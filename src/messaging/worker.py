import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from typing import Protocol, cast

from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError

from src.infrastructure.database.session import (
    async_session_factory,
    engine,
)
from src.knowledge.repository import KnowledgeRepository
from src.messaging.connection import create_rabbitmq_connection
from src.messaging.contracts import OutboxMessage
from src.messaging.factory import create_ingestion_service
from src.messaging.repository import ProcessedMessageRepository
from src.messaging.retry import RetryChannel, publish_retry_or_dlq
from src.messaging.task_events import (
    TASK_DELETED_EVENT,
    TASK_STATUS_CHANGED_EVENT,
    TaskEventContractError,
    is_indexable_task_event,
    task_event_to_index_command,
    validate_task_deleted_event,
)
from src.messaging.topology import (
    AI_TASK_QUEUE,
    declare_ai_topology,
)

logger = logging.getLogger(__name__)


class ConsumerQueue(Protocol):
    async def consume(
        self,
        callback: Callable[
            [AbstractIncomingMessage],
            Awaitable[None],
        ],
    ) -> object: ...


async def process_event(
    event: OutboxMessage,
) -> None:
    if event.aggregate_type != "task":
        logger.debug(
            "Unsupported aggregate ignored: %s",
            event.aggregate_type,
        )
        return

    index_command = None

    if is_indexable_task_event(event):
        index_command = task_event_to_index_command(event)

    if event.event_type == TASK_DELETED_EVENT:
        validate_task_deleted_event(event)

    async with async_session_factory() as session:
        processed_repository = ProcessedMessageRepository(session)

        claimed = await processed_repository.claim_event(event)

        if not claimed:
            logger.info(
                "Duplicate AI event ignored: %s",
                event.event_id,
            )
            return

        latest_version = await processed_repository.get_latest_aggregate_version(
            organization_id=event.organization_id,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            exclude_event_id=event.event_id,
        )

        if latest_version is not None and event.event_version <= latest_version:
            await session.commit()

            logger.info(
                "Stale AI event ignored: event_id=%s version=%s latest_version=%s",
                event.event_id,
                event.event_version,
                latest_version,
            )
            return

        if is_indexable_task_event(event):
            assert index_command is not None

            ingestion_service = create_ingestion_service(session)

            source = await ingestion_service.index_source(index_command)

            await session.commit()

            logger.info(
                "Task indexed: task_id=%s source_id=%s source_version=%s",
                event.aggregate_id,
                source.id,
                source.source_version,
            )
            return

        if event.event_type == TASK_STATUS_CHANGED_EVENT:
            await session.commit()

            logger.info(
                "Task status event does not change indexed content: %s",
                event.aggregate_id,
            )
            return

        if event.event_type == TASK_DELETED_EVENT:
            validate_task_deleted_event(event)
            organization_id = event.organization_id

            if organization_id is None:
                raise TaskEventContractError(
                    "Task deleted event does not contain organization_id"
                )

            repository = KnowledgeRepository(session)

            deleted_count = await repository.delete_source(
                organization_id=organization_id,
                source_type="task",
                source_entity_id=event.aggregate_id,
            )

            await session.commit()

            logger.info(
                "Task source deleted: task_id=%s deleted_count=%s version=%s",
                event.aggregate_id,
                deleted_count,
                event.event_version,
            )
            return

        await session.commit()

        logger.debug(
            "Unsupported task event ignored: %s",
            event.event_type,
        )


async def process_message(
    message: AbstractIncomingMessage,
) -> None:
    try:
        event = OutboxMessage.model_validate_json(
            message.body,
        )

    except ValidationError:
        logger.exception(
            "Invalid RabbitMQ message",
        )

        await message.reject(
            requeue=False,
        )
        return

    logger.info(
        "AI event received: type=%s event_id=%s aggregate_id=%s",
        event.event_type,
        event.event_id,
        event.aggregate_id,
    )

    try:
        await process_event(event)

    except TaskEventContractError:
        logger.exception(
            "Permanent task event contract error: %s",
            event.event_id,
        )

        await message.reject(
            requeue=False,
        )
        return

    except Exception as exc:
        logger.exception(
            "Failed to process AI event: %s",
            event.event_id,
        )

        try:
            await publish_retry_or_dlq(
                channel=cast(RetryChannel, message.channel),
                message=message,
                error=exc,
            )
        except Exception:
            logger.exception(
                "Failed to schedule AI event retry: %s",
                event.event_id,
            )

            await message.nack(
                requeue=True,
            )
            return

        await message.ack()
        return

    await message.ack()

    logger.info(
        "AI event processed: %s",
        event.event_id,
    )


def install_shutdown_handlers(
    stop_event: asyncio.Event,
) -> None:
    def shutdown(signal_name: str) -> None:
        logger.info(
            "Received %s, shutting down",
            signal_name,
        )
        stop_event.set()

    loop = asyncio.get_running_loop()

    for sig in (
        signal.SIGTERM,
        signal.SIGINT,
    ):
        loop.add_signal_handler(
            sig,
            shutdown,
            sig.name,
        )


async def consume_until_stopped(
    queue: ConsumerQueue,
    stop_event: asyncio.Event,
) -> None:
    await queue.consume(
        process_message,
    )

    await stop_event.wait()


async def run_worker() -> None:
    connection = await create_rabbitmq_connection()

    await declare_ai_topology(
        connection,
    )

    channel = await connection.channel()

    await channel.set_qos(
        prefetch_count=10,
    )

    queue = await channel.get_queue(
        AI_TASK_QUEUE,
        ensure=True,
    )

    stop_event = asyncio.Event()

    install_shutdown_handlers(
        stop_event,
    )

    logger.info(
        "FlowForge AI worker started. Queue: %s",
        AI_TASK_QUEUE,
    )

    try:
        await consume_until_stopped(
            queue,
            stop_event,
        )

    finally:
        logger.info(
            "Stopping FlowForge AI worker",
        )

        await channel.close()
        await connection.close()
        await engine.dispose()

        logger.info(
            "FlowForge AI worker stopped",
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s %(levelname)s %(name)s: %(message)s"),
    )

    asyncio.run(
        run_worker(),
    )


if __name__ == "__main__":
    main()
