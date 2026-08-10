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
        self.headers: dict[str, object] | None = None
        self.channel = object()
        self.ack = AsyncMock()
        self.nack = AsyncMock()
        self.reject = AsyncMock()


def make_message(
    payload: dict[str, object],
    *,
    event_type: str = "task.created",
) -> FakeMessage:
    event = OutboxMessage(
        event_id=uuid.uuid4(),
        event_type=event_type,
        event_version=1,
        aggregate_type="task",
        aggregate_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        occurred_at=datetime.now(UTC),
        payload=payload,
    )

    return FakeMessage(event.model_dump_json().encode("utf-8"))


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


class FakeProcessedMessageRepository:
    instances: list["FakeProcessedMessageRepository"] = []
    claimed: bool = True
    latest_version: int | None = None

    def __init__(
        self,
        session: object,
    ) -> None:
        self.session = session
        self.claim_event = AsyncMock(return_value=self.claimed)
        self.get_latest_aggregate_version = AsyncMock(return_value=self.latest_version)
        self.instances.append(self)


def install_fake_processed_repository(
    monkeypatch: pytest.MonkeyPatch,
    *,
    claimed: bool = True,
    latest_version: int | None = None,
) -> None:
    FakeProcessedMessageRepository.instances = []
    FakeProcessedMessageRepository.claimed = claimed
    FakeProcessedMessageRepository.latest_version = latest_version

    monkeypatch.setattr(
        "src.messaging.worker.ProcessedMessageRepository",
        FakeProcessedMessageRepository,
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


@pytest.mark.asyncio
async def test_process_message_schedules_retry_for_transient_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = make_message(
        {
            "task_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "title": "Retry me",
        }
    )
    publish_retry_or_dlq = AsyncMock()

    async def failing_process_event(
        event: OutboxMessage,
    ) -> None:
        raise RuntimeError("Ollama unavailable")

    monkeypatch.setattr(
        "src.messaging.worker.process_event",
        failing_process_event,
    )
    monkeypatch.setattr(
        "src.messaging.worker.publish_retry_or_dlq",
        publish_retry_or_dlq,
    )

    await process_message(message)  # type: ignore[arg-type]

    publish_retry_or_dlq.assert_awaited_once()
    message.ack.assert_awaited_once_with()
    message.nack.assert_not_awaited()
    message.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_message_requeues_when_retry_scheduling_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = make_message(
        {
            "task_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "title": "Retry me",
        }
    )

    async def failing_process_event(
        event: OutboxMessage,
    ) -> None:
        raise RuntimeError("Ollama unavailable")

    async def failing_publish_retry_or_dlq(
        **kwargs: object,
    ) -> bool:
        raise RuntimeError("RabbitMQ unavailable")

    monkeypatch.setattr(
        "src.messaging.worker.process_event",
        failing_process_event,
    )
    monkeypatch.setattr(
        "src.messaging.worker.publish_retry_or_dlq",
        failing_publish_retry_or_dlq,
    )

    await process_message(message)  # type: ignore[arg-type]

    message.nack.assert_awaited_once_with(
        requeue=True,
    )
    message.ack.assert_not_awaited()
    message.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_event_deletes_task_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization_id = uuid.uuid4()
    task_id = uuid.uuid4()
    session = FakeSession()
    FakeKnowledgeRepository.instances = []
    install_fake_processed_repository(monkeypatch)

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


@pytest.mark.asyncio
async def test_process_event_ignores_duplicate_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    install_fake_processed_repository(
        monkeypatch,
        claimed=False,
    )
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
        event_version=2,
        aggregate_type="task",
        aggregate_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        occurred_at=datetime.now(UTC),
        payload={
            "task_id": str(uuid.uuid4()),
        },
    )

    await process_event(event)

    processed_repository = FakeProcessedMessageRepository.instances[0]
    processed_repository.claim_event.assert_awaited_once_with(event)
    processed_repository.get_latest_aggregate_version.assert_not_awaited()
    assert FakeKnowledgeRepository.instances == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_event_commits_and_ignores_stale_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    organization_id = uuid.uuid4()
    task_id = uuid.uuid4()
    install_fake_processed_repository(
        monkeypatch,
        latest_version=6,
    )
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
        event_version=5,
        aggregate_type="task",
        aggregate_id=task_id,
        organization_id=organization_id,
        occurred_at=datetime.now(UTC),
        payload={
            "task_id": str(task_id),
        },
    )

    await process_event(event)

    processed_repository = FakeProcessedMessageRepository.instances[0]
    processed_repository.get_latest_aggregate_version.assert_awaited_once_with(
        organization_id=organization_id,
        aggregate_type="task",
        aggregate_id=task_id,
        exclude_event_id=event.event_id,
    )
    assert FakeKnowledgeRepository.instances == []
    session.commit.assert_awaited_once_with()
