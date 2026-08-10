import uuid
from datetime import UTC, datetime

import pytest

from src.messaging.contracts import OutboxMessage
from src.messaging.task_events import (
    TaskEventContractError,
    is_indexable_task_event,
    task_event_to_index_command,
)


def make_event(
    *,
    event_type: str = "task.created",
    organization_id: uuid.UUID | None = None,
    payload: dict[str, object] | None = None,
) -> OutboxMessage:
    task_id = uuid.uuid4()

    return OutboxMessage(
        event_id=uuid.uuid4(),
        event_type=event_type,
        event_version=1,
        aggregate_type="task",
        aggregate_id=task_id,
        organization_id=organization_id,
        occurred_at=datetime.now(UTC),
        payload=payload
        if payload is not None
        else {
            "task_id": str(task_id),
            "project_id": str(uuid.uuid4()),
            "title": "Ship RabbitMQ sync",
            "description": "Publish task events for AI indexing",
            "status": "todo",
            "priority": "high",
        },
    )


def test_task_event_to_index_command_maps_api_task_event() -> None:
    organization_id = uuid.uuid4()
    event = make_event(
        organization_id=organization_id,
    )

    command = task_event_to_index_command(event)

    assert command.organization_id == organization_id
    assert command.source_type == "task"
    assert command.source_entity_id == event.aggregate_id
    assert command.title == "Ship RabbitMQ sync"
    assert "Задача: Ship RabbitMQ sync" in command.content
    assert "Описание: Publish task events for AI indexing" in command.content
    assert "Статус: todo" in command.content
    assert "Приоритет: high" in command.content
    assert command.metadata["event_type"] == "task.created"
    assert command.metadata["task_id"] == str(event.aggregate_id)


def test_current_flowforge_api_task_created_contract_is_not_indexable() -> None:
    event = make_event(
        payload={
            "task_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        },
    )

    with pytest.raises(
        TaskEventContractError,
        match="organization_id",
    ):
        task_event_to_index_command(event)


def test_task_event_requires_title_after_organization_is_present() -> None:
    event = make_event(
        organization_id=uuid.uuid4(),
        payload={
            "task_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
        },
    )

    with pytest.raises(
        TaskEventContractError,
        match="non-empty title",
    ):
        task_event_to_index_command(event)


def test_status_changed_is_not_indexable_content_event() -> None:
    event = make_event(
        event_type="task.status_changed",
        organization_id=uuid.uuid4(),
        payload={
            "task_id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "old_status": "todo",
            "new_status": "done",
        },
    )

    assert is_indexable_task_event(event) is False
