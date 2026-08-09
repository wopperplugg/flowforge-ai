import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from typing import Protocol

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from pydantic import ValidationError

from src.config import settings
from src.infrastructure.database.session import (
    async_session_factory,
    engine,
)
from src.messaging.contracts import OutboxMessage
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
    match event.event_type:
        case "task.created":
            logger.info(
                "Task created received: %s",
                event.aggregate_id,
            )

        case "task.updated":
            logger.info(
                "Task updated received: %s",
                event.aggregate_id,
            )

        case "task.deleted":
            logger.info(
                "Task deleted received: %s",
                event.aggregate_id,
            )

        case _:
            logger.debug(
                "Unsupported event ignored: %s",
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
        async with async_session_factory() as session:
            async with session.begin():
                await process_event(event)

    except Exception:
        logger.exception(
            "Failed to process AI event: %s",
            event.event_id,
        )

        await message.nack(
            requeue=True,
        )
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
    connection = await aio_pika.connect_robust(
        settings.rabbitmq_dsn.unicode_string(),
    )

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
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s: "
            "%(message)s"
        ),
    )

    asyncio.run(
        run_worker(),
    )


if __name__ == "__main__":
    main()