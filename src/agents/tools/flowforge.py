import json
import uuid
from datetime import date
from typing import Any, Protocol

from langchain.tools import tool
from pydantic import ValidationError

from src.flowforge_api.client import (
    FlowForgeAPIClient,
    FlowForgeAPIError,
    FlowForgeAPIUnavailableError,
)
from src.flowforge_api.schemas import (
    TaskCreate,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
)


class ApprovalRepository(Protocol):
    async def create_approval(
        self,
        **kwargs: Any,
    ) -> Any: ...


def create_flowforge_read_tools(
    *,
    client: FlowForgeAPIClient,
) -> list[Any]:
    @tool
    async def get_project(project_id: str) -> str:
        """Get a FlowForge project by id using the authenticated user's access."""
        try:
            project = await client.get_project(uuid.UUID(project_id))
        except (ValueError, FlowForgeAPIError, FlowForgeAPIUnavailableError) as exc:
            return _tool_error(exc)

        return project.model_dump_json()

    @tool
    async def list_tasks(project_id: str, limit: int = 20, offset: int = 0) -> str:
        """List FlowForge tasks in a project using the authenticated user's access."""
        try:
            page = await client.list_tasks(
                uuid.UUID(project_id),
                limit=limit,
                offset=offset,
            )
        except (ValueError, FlowForgeAPIError, FlowForgeAPIUnavailableError) as exc:
            return _tool_error(exc)

        return page.model_dump_json()

    @tool
    async def get_task(task_id: str) -> str:
        """Get a FlowForge task by id using the authenticated user's access."""
        try:
            task = await client.get_task(uuid.UUID(task_id))
        except (ValueError, FlowForgeAPIError, FlowForgeAPIUnavailableError) as exc:
            return _tool_error(exc)

        return task.model_dump_json()

    return [
        get_project,
        list_tasks,
        get_task,
    ]


def create_flowforge_write_tools(
    *,
    client: FlowForgeAPIClient,
    approved: bool,
    approval_repository: ApprovalRepository | None = None,
    thread_id: str | None = None,
    organization_id: uuid.UUID | None = None,
    project_context_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> list[Any]:
    @tool
    async def create_task(
        project_id: str,
        title: str,
        description: str | None = None,
        priority: str = TaskPriority.MEDIUM.value,
        assigned_to_id: str | None = None,
        due_date: str | None = None,
    ) -> str:
        """Create a FlowForge task after external human approval has been granted."""
        if not approved:
            return await _approval_required(
                approval_repository=approval_repository,
                thread_id=thread_id,
                organization_id=organization_id,
                project_id=project_context_id,
                user_id=user_id,
                tool_name="create_task",
                arguments={
                    "project_id": project_id,
                    "title": title,
                    "description": description,
                    "priority": priority,
                    "assigned_to_id": assigned_to_id,
                    "due_date": due_date,
                },
            )

        try:
            task = await client.create_task(
                uuid.UUID(project_id),
                TaskCreate(
                    title=title,
                    description=description,
                    priority=TaskPriority(priority),
                    assigned_to_id=_uuid_or_none(assigned_to_id),
                    due_date=_date_or_none(due_date),
                ),
            )
        except (
            ValueError,
            ValidationError,
            FlowForgeAPIError,
            FlowForgeAPIUnavailableError,
        ) as exc:
            return _tool_error(exc)

        return task.model_dump_json()

    @tool
    async def update_task(
        task_id: str,
        version: int,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        assigned_to_id: str | None = None,
        due_date: str | None = None,
    ) -> str:
        """Update a FlowForge task after external human approval has been granted."""
        if not approved:
            return await _approval_required(
                approval_repository=approval_repository,
                thread_id=thread_id,
                organization_id=organization_id,
                project_id=project_context_id,
                user_id=user_id,
                tool_name="update_task",
                arguments={
                    "task_id": task_id,
                    "version": version,
                    "title": title,
                    "description": description,
                    "status": status,
                    "priority": priority,
                    "assigned_to_id": assigned_to_id,
                    "due_date": due_date,
                },
            )

        try:
            task = await client.update_task(
                uuid.UUID(task_id),
                TaskUpdate(
                    title=title,
                    description=description,
                    status=TaskStatus(status) if status is not None else None,
                    priority=TaskPriority(priority) if priority is not None else None,
                    assigned_to_id=_uuid_or_none(assigned_to_id),
                    due_date=_date_or_none(due_date),
                    version=version,
                ),
            )
        except (
            ValueError,
            ValidationError,
            FlowForgeAPIError,
            FlowForgeAPIUnavailableError,
        ) as exc:
            return _tool_error(exc)

        return task.model_dump_json()

    @tool
    async def delete_task(
        project_id: str,
        task_id: str,
    ) -> str:
        """Delete a FlowForge task after external human approval has been granted."""
        if not approved:
            return await _approval_required(
                approval_repository=approval_repository,
                thread_id=thread_id,
                organization_id=organization_id,
                project_id=project_context_id,
                user_id=user_id,
                tool_name="delete_task",
                arguments={
                    "project_id": project_id,
                    "task_id": task_id,
                },
            )

        try:
            await client.delete_task(
                project_id=uuid.UUID(project_id),
                task_id=uuid.UUID(task_id),
            )
        except (
            ValueError,
            FlowForgeAPIError,
            FlowForgeAPIUnavailableError,
        ) as exc:
            return _tool_error(exc)

        return json.dumps(
            {
                "status": "deleted",
                "task_id": task_id,
            }
        )

    return [
        create_task,
        update_task,
        delete_task,
    ]


async def _approval_required(
    *,
    approval_repository: ApprovalRepository | None,
    thread_id: str | None,
    organization_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    approval_id: str | None = None

    if (
        approval_repository is not None
        and thread_id is not None
        and organization_id is not None
        and project_id is not None
        and user_id is not None
    ):
        approval = await approval_repository.create_approval(
            thread_id=thread_id,
            organization_id=organization_id,
            project_id=project_id,
            user_id=user_id,
            tool_name=tool_name,
            arguments=arguments,
        )
        approval_id = str(approval.id)

    return json.dumps(
        {
            "status": "approval_required",
            "approval_id": approval_id,
            "tool": tool_name,
            "arguments": arguments,
            "message": "Human approval is required before executing this write tool.",
        }
    )


def _tool_error(exc: Exception) -> str:
    if isinstance(exc, FlowForgeAPIError):
        return json.dumps(
            {
                "status": "error",
                "status_code": exc.status_code,
                "message": exc.message,
            }
        )

    return json.dumps(
        {
            "status": "error",
            "message": str(exc),
        }
    )


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None

    return uuid.UUID(value)


def _date_or_none(value: str | None) -> date | None:
    if value is None:
        return None

    return date.fromisoformat(value)
