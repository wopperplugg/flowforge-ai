from uuid import UUID

from src.ingestion.schemas import IndexSourceCommand
from src.messaging.contracts import OutboxMessage


class TaskEventContractError(ValueError):
    """Permanent task event contract error."""


INDEXABLE_TASK_EVENTS = frozenset(
    {
        "task.created",
        "task.updated",
    }
)

TASK_STATUS_CHANGED_EVENT = "task.status_changed"


def is_indexable_task_event(
    event: OutboxMessage,
) -> bool:
    return (
        event.aggregate_type == "task"
        and event.event_type in INDEXABLE_TASK_EVENTS
    )


def task_event_to_index_command(
    event: OutboxMessage,
) -> IndexSourceCommand:
    if event.aggregate_type != "task":
        raise TaskEventContractError(
            f"Unsupported aggregate_type for task indexing: {event.aggregate_type}"
        )

    if event.event_type not in INDEXABLE_TASK_EVENTS:
        raise TaskEventContractError(
            f"Unsupported task indexing event_type: {event.event_type}"
        )

    if event.organization_id is None:
        raise TaskEventContractError(
            "Task event does not contain organization_id"
        )

    title = event.payload.get("title")
    description = event.payload.get("description")
    project_id_raw = event.payload.get("project_id")

    if not isinstance(title, str) or not title.strip():
        raise TaskEventContractError(
            "Task event must contain non-empty title"
        )

    if (
        description is not None
        and not isinstance(description, str)
    ):
        raise TaskEventContractError(
            "Task description must be a string"
        )

    project_id: UUID | None = None

    if project_id_raw is not None:
        try:
            project_id = UUID(str(project_id_raw))
        except ValueError as exc:
            raise TaskEventContractError(
                "Task event project_id must be a UUID"
            ) from exc

    content_parts = [
        f"Задача: {title.strip()}",
    ]

    if description and description.strip():
        content_parts.append(
            f"Описание: {description.strip()}"
        )

    for label, payload_key in (
        ("Статус", "status"),
        ("Приоритет", "priority"),
        ("Срок", "due_date"),
    ):
        value = event.payload.get(payload_key)

        if isinstance(value, str) and value.strip():
            content_parts.append(
                f"{label}: {value.strip()}"
            )

    return IndexSourceCommand(
        organization_id=event.organization_id,
        project_id=project_id,
        source_type="task",
        source_entity_id=event.aggregate_id,
        title=title.strip(),
        content="\n\n".join(content_parts),
        metadata={
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "task_id": str(event.aggregate_id),
        },
    )
