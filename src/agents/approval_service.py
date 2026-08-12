import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.conversation_models import AssistantToolApproval
from src.agents.conversation_repository import AssistantConversationRepository
from src.agents.rag.schemas import ToolApprovalExecutionResponse, ToolApprovalResponse
from src.flowforge_api.client import FlowForgeAPIClient
from src.flowforge_api.schemas import TaskCreate, TaskPriority, TaskStatus, TaskUpdate


class ToolApprovalNotFoundError(RuntimeError):
    pass


class ToolApprovalInvalidStateError(RuntimeError):
    pass


class ToolApprovalExecutionError(RuntimeError):
    pass


class AssistantApprovalService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        flowforge_client: FlowForgeAPIClient,
    ) -> None:
        self._session = session
        self._flowforge_client = flowforge_client
        self._repository = AssistantConversationRepository(session)

    async def approve(
        self,
        *,
        approval_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ToolApprovalResponse:
        approval = await self._get_approval(
            approval_id=approval_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if approval.status != "pending":
            raise ToolApprovalInvalidStateError(
                "Only pending approvals can be approved"
            )

        await self._repository.set_approval_status(approval, "approved")
        await self._session.commit()
        return _approval_response(approval)

    async def reject(
        self,
        *,
        approval_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ToolApprovalResponse:
        approval = await self._get_approval(
            approval_id=approval_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if approval.status != "pending":
            raise ToolApprovalInvalidStateError(
                "Only pending approvals can be rejected"
            )

        await self._repository.set_approval_status(approval, "rejected")
        await self._session.commit()
        return _approval_response(approval)

    async def execute(
        self,
        *,
        approval_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ToolApprovalExecutionResponse:
        approval = await self._get_approval(
            approval_id=approval_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if approval.status != "approved":
            raise ToolApprovalInvalidStateError("Only approved tools can be executed")

        result = await self._execute_approval(approval)
        await self._repository.set_approval_status(
            approval,
            "executed",
            result=result,
        )
        await self._repository.add_message(
            thread_id=approval.thread_id,
            role="tool",
            content=f"Executed {approval.tool_name}",
            metadata={
                "approval_id": str(approval.id),
                "result": result,
            },
        )
        await self._session.commit()
        return ToolApprovalExecutionResponse(
            approval=_approval_response(approval),
            result=result,
        )

    async def _get_approval(
        self,
        *,
        approval_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AssistantToolApproval:
        approval = await self._repository.get_approval_for_user(
            approval_id=approval_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        if approval is None:
            raise ToolApprovalNotFoundError("Tool approval was not found")

        return approval

    async def _execute_approval(
        self,
        approval: AssistantToolApproval,
    ) -> dict[str, Any]:
        arguments = approval.arguments

        if approval.tool_name == "create_task":
            task = await self._flowforge_client.create_task(
                uuid.UUID(str(arguments["project_id"])),
                TaskCreate(
                    title=str(arguments["title"]),
                    description=_str_or_none(arguments.get("description")),
                    priority=TaskPriority(
                        str(arguments.get("priority") or TaskPriority.MEDIUM.value)
                    ),
                    assigned_to_id=_uuid_or_none(arguments.get("assigned_to_id")),
                    due_date=_date_or_none(arguments.get("due_date")),
                ),
            )
            return task.model_dump(mode="json")

        if approval.tool_name == "update_task":
            task = await self._flowforge_client.update_task(
                uuid.UUID(str(arguments["task_id"])),
                TaskUpdate(
                    title=_str_or_none(arguments.get("title")),
                    description=_str_or_none(arguments.get("description")),
                    status=(
                        TaskStatus(str(arguments["status"]))
                        if arguments.get("status") is not None
                        else None
                    ),
                    priority=(
                        TaskPriority(str(arguments["priority"]))
                        if arguments.get("priority") is not None
                        else None
                    ),
                    assigned_to_id=_uuid_or_none(arguments.get("assigned_to_id")),
                    due_date=_date_or_none(arguments.get("due_date")),
                    version=int(arguments["version"]),
                ),
            )
            return task.model_dump(mode="json")

        if approval.tool_name == "delete_task":
            await self._flowforge_client.delete_task(
                project_id=uuid.UUID(str(arguments["project_id"])),
                task_id=uuid.UUID(str(arguments["task_id"])),
            )
            return {
                "status": "deleted",
                "task_id": str(arguments["task_id"]),
            }

        raise ToolApprovalExecutionError(f"Unsupported tool: {approval.tool_name}")


def _approval_response(approval: AssistantToolApproval) -> ToolApprovalResponse:
    return ToolApprovalResponse(
        id=approval.id,
        thread_id=approval.thread_id,
        tool_name=approval.tool_name,
        arguments=approval.arguments,
        status=approval.status,
        result=approval.result,
    )


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None

    return str(value)


def _uuid_or_none(value: object) -> uuid.UUID | None:
    if value is None:
        return None

    return uuid.UUID(str(value))


def _date_or_none(value: object) -> date | None:
    if value is None:
        return None

    return date.fromisoformat(str(value))
