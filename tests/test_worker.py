import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.messaging.contracts import OutboxMessage
from src.messaging.worker import process_message


class FakeMessage:
    def __init__(
        self,
        body: bytes,
    ) -> None:
        self.body = body
        self.ack = AsyncMock()
        self.nack = AsyncMock()
        self.reject = AsyncMock()


def make_message(
    payload: dict[str, object],
) -> FakeMessage:
    event = OutboxMessage(
        event_id=uuid.uuid4(),
        event_type="task.created",
        event_version=1,
        aggregate_type="task",
        aggregate_id=uuid.uuid4(),
        occurred_at=datetime.now(UTC),
        payload=payload,
    )

    return FakeMessage(
        event.model_dump_json().encode("utf-8")
    )


@pytest.mark.asyncio
async def test_process_message_rejects_permanent_contract_errors() -> None:
    message = make_message(
        {
            "task_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        }
    )

    await process_message(message)  # type: ignore[arg-type]

    message.reject.assert_awaited_once_with(
        requeue=False,
    )
    message.nack.assert_not_awaited()
    message.ack.assert_not_awaited()
