import logging
from typing import Protocol

from aio_pika import DeliveryMode, Message
from aio_pika.abc import (
    AbstractExchange,
    AbstractIncomingMessage,
    FieldValue,
)

from src.messaging.topology import (
    AI_DLX_EXCHANGE,
    AI_RETRY_EXCHANGE,
    AI_TASK_DLQ_ROUTING_KEY,
    AI_TASK_RETRY_10S_ROUTING_KEY,
    AI_TASK_RETRY_60S_ROUTING_KEY,
)

logger = logging.getLogger(__name__)

AI_RETRY_COUNT_HEADER = "x-ai-retry-count"
MAX_AI_RETRY_COUNT = 2


class RetryChannel(Protocol):
    async def get_exchange(
        self,
        name: str,
        *,
        ensure: bool = True,
    ) -> AbstractExchange: ...


def get_retry_count(
    message: AbstractIncomingMessage,
) -> int:
    headers = message.headers or {}
    raw_retry_count = headers.get(AI_RETRY_COUNT_HEADER, 0)

    if isinstance(raw_retry_count, int):
        return max(raw_retry_count, 0)

    if isinstance(raw_retry_count, str) and raw_retry_count.isdigit():
        return int(raw_retry_count)

    return 0


def get_retry_routing_key(
    retry_count: int,
) -> str | None:
    match retry_count:
        case 0:
            return AI_TASK_RETRY_10S_ROUTING_KEY
        case 1:
            return AI_TASK_RETRY_60S_ROUTING_KEY
        case _:
            return None


def build_retry_message(
    message: AbstractIncomingMessage,
    *,
    retry_count: int,
    error: str,
) -> Message:
    headers: dict[str, FieldValue] = dict(message.headers or {})
    headers[AI_RETRY_COUNT_HEADER] = retry_count
    headers["x-ai-last-error"] = error[:500]

    return Message(
        body=message.body,
        content_type=message.content_type,
        content_encoding=message.content_encoding,
        delivery_mode=DeliveryMode.PERSISTENT,
        headers=headers,
        correlation_id=message.correlation_id,
        message_id=message.message_id,
        timestamp=message.timestamp,
        type=message.type,
    )


async def publish_retry_or_dlq(
    *,
    channel: RetryChannel,
    message: AbstractIncomingMessage,
    error: Exception,
) -> bool:
    current_retry_count = get_retry_count(message)
    next_retry_count = current_retry_count + 1
    routing_key = get_retry_routing_key(current_retry_count)

    retry_message = build_retry_message(
        message,
        retry_count=next_retry_count,
        error=str(error),
    )

    if routing_key is None:
        dlx_exchange = await channel.get_exchange(
            AI_DLX_EXCHANGE,
            ensure=True,
        )
        await dlx_exchange.publish(
            retry_message,
            routing_key=AI_TASK_DLQ_ROUTING_KEY,
        )

        logger.error(
            "AI message sent to DLQ after retries: message_id=%s retry_count=%s",
            message.message_id,
            current_retry_count,
        )
        return False

    retry_exchange = await channel.get_exchange(
        AI_RETRY_EXCHANGE,
        ensure=True,
    )
    await retry_exchange.publish(
        retry_message,
        routing_key=routing_key,
    )

    logger.warning(
        "AI message scheduled for retry: message_id=%s retry_count=%s routing_key=%s",
        message.message_id,
        next_retry_count,
        routing_key,
    )

    return True
