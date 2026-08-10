from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.messaging.retry import (
    AI_RETRY_COUNT_HEADER,
    build_retry_message,
    get_retry_count,
    get_retry_routing_key,
    publish_retry_or_dlq,
)
from src.messaging.topology import (
    AI_DLX_EXCHANGE,
    AI_RETRY_EXCHANGE,
    AI_TASK_DLQ_ROUTING_KEY,
    AI_TASK_RETRY_10S_ROUTING_KEY,
    AI_TASK_RETRY_60S_ROUTING_KEY,
)


class FakeIncomingMessage:
    def __init__(
        self,
        *,
        headers: dict[str, object] | None = None,
    ) -> None:
        self.body = b"{}"
        self.headers = headers
        self.content_type = "application/json"
        self.content_encoding = "utf-8"
        self.correlation_id = "correlation-id"
        self.message_id = "message-id"
        self.timestamp = datetime.now(UTC)
        self.type = "task.created"


class FakeChannel:
    def __init__(self) -> None:
        self.exchanges: dict[str, FakeExchange] = {}
        self.get_exchange = AsyncMock(side_effect=self._get_exchange)

    async def _get_exchange(
        self,
        name: str,
        *,
        ensure: bool = True,
    ) -> "FakeExchange":
        exchange = FakeExchange()
        self.exchanges[name] = exchange
        return exchange


class FakeExchange:
    def __init__(self) -> None:
        self.publish = AsyncMock()


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        (None, 0),
        ({AI_RETRY_COUNT_HEADER: 2}, 2),
        ({AI_RETRY_COUNT_HEADER: "3"}, 3),
        ({AI_RETRY_COUNT_HEADER: -1}, 0),
        ({AI_RETRY_COUNT_HEADER: "bad"}, 0),
    ],
)
def test_get_retry_count(
    headers: dict[str, object] | None,
    expected: int,
) -> None:
    assert get_retry_count(FakeIncomingMessage(headers=headers)) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("retry_count", "expected"),
    [
        (0, AI_TASK_RETRY_10S_ROUTING_KEY),
        (1, AI_TASK_RETRY_60S_ROUTING_KEY),
        (2, None),
    ],
)
def test_get_retry_routing_key(
    retry_count: int,
    expected: str | None,
) -> None:
    assert get_retry_routing_key(retry_count) == expected


def test_build_retry_message_preserves_body_and_sets_headers() -> None:
    source_message = FakeIncomingMessage(
        headers={
            "existing": "value",
        }
    )

    retry_message = build_retry_message(
        source_message,  # type: ignore[arg-type]
        retry_count=1,
        error="x" * 600,
    )

    assert retry_message.body == source_message.body
    assert retry_message.headers is not None
    assert retry_message.headers["existing"] == "value"
    assert retry_message.headers[AI_RETRY_COUNT_HEADER] == 1
    assert retry_message.headers["x-ai-last-error"] == "x" * 500


@pytest.mark.asyncio
async def test_publish_retry_or_dlq_schedules_first_retry() -> None:
    channel = FakeChannel()
    message = FakeIncomingMessage()

    scheduled = await publish_retry_or_dlq(
        channel=channel,
        message=message,  # type: ignore[arg-type]
        error=RuntimeError("Ollama unavailable"),
    )

    assert scheduled is True
    channel.get_exchange.assert_awaited_once_with(
        AI_RETRY_EXCHANGE,
        ensure=True,
    )
    exchange = channel.exchanges[AI_RETRY_EXCHANGE]
    exchange.publish.assert_awaited_once()
    publish_call = exchange.publish.await_args
    assert publish_call is not None
    assert publish_call.kwargs["routing_key"] == AI_TASK_RETRY_10S_ROUTING_KEY


@pytest.mark.asyncio
async def test_publish_retry_or_dlq_sends_exhausted_message_to_dlq() -> None:
    channel = FakeChannel()
    message = FakeIncomingMessage(
        headers={
            AI_RETRY_COUNT_HEADER: 2,
        }
    )

    scheduled = await publish_retry_or_dlq(
        channel=channel,
        message=message,  # type: ignore[arg-type]
        error=RuntimeError("Ollama unavailable"),
    )

    assert scheduled is False
    channel.get_exchange.assert_awaited_once_with(
        AI_DLX_EXCHANGE,
        ensure=True,
    )
    exchange = channel.exchanges[AI_DLX_EXCHANGE]
    exchange.publish.assert_awaited_once()
    publish_call = exchange.publish.await_args
    assert publish_call is not None
    assert publish_call.kwargs["routing_key"] == AI_TASK_DLQ_ROUTING_KEY
