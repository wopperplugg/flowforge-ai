import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.conversation_models import (
    AssistantMessage,
    AssistantThread,
    AssistantToolApproval,
)


class AssistantConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_thread(
        self,
        *,
        thread_id: str,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AssistantThread:
        thread = await self._session.get(AssistantThread, thread_id)

        if thread is None:
            thread = AssistantThread(
                id=thread_id,
                organization_id=organization_id,
                project_id=project_id,
                user_id=user_id,
            )
            self._session.add(thread)
            await self._session.flush()
            return thread

        if (
            thread.organization_id != organization_id
            or thread.project_id != project_id
            or thread.user_id != user_id
        ):
            raise ValueError("Assistant thread does not belong to this context")

        await self._session.flush()
        return thread

    async def add_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> AssistantMessage:
        message = AssistantMessage(
            thread_id=thread_id,
            role=role,
            content=content,
            message_metadata=metadata or {},
        )
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_messages(
        self,
        *,
        thread_id: str,
        limit: int = 20,
    ) -> list[AssistantMessage]:
        statement = (
            select(AssistantMessage)
            .where(AssistantMessage.thread_id == thread_id)
            .order_by(AssistantMessage.created_at.desc())
            .limit(limit)
        )
        result = await self._session.scalars(statement)
        return list(reversed(result.all()))

    async def create_approval(
        self,
        *,
        thread_id: str,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> AssistantToolApproval:
        approval = AssistantToolApproval(
            thread_id=thread_id,
            organization_id=organization_id,
            project_id=project_id,
            user_id=user_id,
            tool_name=tool_name,
            arguments=arguments,
            status="pending",
        )
        self._session.add(approval)
        await self._session.flush()
        return approval

    async def get_approval_for_user(
        self,
        *,
        approval_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AssistantToolApproval | None:
        statement = select(AssistantToolApproval).where(
            AssistantToolApproval.id == approval_id,
            AssistantToolApproval.organization_id == organization_id,
            AssistantToolApproval.user_id == user_id,
        )
        return cast(
            AssistantToolApproval | None,
            await self._session.scalar(statement),
        )

    async def set_approval_status(
        self,
        approval: AssistantToolApproval,
        status: str,
        *,
        result: dict[str, Any] | None = None,
    ) -> AssistantToolApproval:
        approval.status = status
        approval.result = result
        await self._session.flush()
        return approval
