import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.messaging.contracts import OutboxMessage
from src.messaging.worker import process_event, process_message


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


class FakeSessionContext:
    def __init__(
        self,
        session: object,
    ) -> None:
        self.session = session

    async def __aenter__(
        self,
    ) -> object:
        return self.session

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        return None


class FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()


class FakeKnowledgeRepository:
    instances: list["FakeKnowledgeRepository"] = []

    def __init__(
        self,
        session: object,
    ) -> None:
        self.session = session
        self.delete_source = AsyncMock(return_value=1)
        self.instances.append(self)


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


@pytest.mark.asyncio
async def test_process_event_deletes_task_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = FakeSession()
    FakeKnowledgeRepository.instances = []

    monkeypatch.setattr(
        "src.messaging.worker.async_session_factory",
        lambda: FakeSessionContext(session),
    )
    monkeypatch.setattr(
        "src.messaging.worker.KnowledgeRepository",
        FakeKnowledgeRepository,
    )

    event = OutboxMessage(
        event_id=uuid.uuid4(),
        event_type="task.deleted",
        event_version=1,
        aggregate_type="task",
        aggregate_id=task_id,
        organization_id=organization_id,
        occurred_at=datetime.now(UTC),
        payload={
            "task_id": str(task_id),
        },
    )

    await process_event(event)

    repository = FakeKnowledgeRepository.instances[0]
    repository.delete_source.assert_awaited_once_with(
        organization_id=organization_id,
        source_type="task",
        source_entity_id=task_id,
    )
    session.commit.assert_awaited_once_with()
