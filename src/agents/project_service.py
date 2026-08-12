import asyncio
import uuid
from collections.abc import Mapping
from typing import Any, Protocol, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.conversation_repository import AssistantConversationRepository
from src.agents.project_agent import create_project_agent
from src.agents.rag.schemas import ProjectAssistantQueryResponse
from src.agents.tools.flowforge import (
    ApprovalRepository,
    create_flowforge_read_tools,
    create_flowforge_write_tools,
)
from src.agents.tools.knowledge import create_search_project_knowledge_tool
from src.config import settings
from src.embeddings.base import EmbeddingProvider
from src.flowforge_api.client import FlowForgeAPIClient


class RunnableAgent(Protocol):
    async def ainvoke(
        self,
        input: Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


class ConversationRepository(Protocol):
    async def ensure_thread(
        self,
        *,
        thread_id: str,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Any: ...

    async def list_messages(
        self,
        *,
        thread_id: str,
        limit: int = 20,
    ) -> list[Any]: ...

    async def add_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any: ...

    async def create_approval(
        self,
        **kwargs: Any,
    ) -> Any: ...


class ProjectAssistantExecutionError(RuntimeError):
    pass


class ProjectAssistantTimeoutError(ProjectAssistantExecutionError):
    pass


class ProjectAssistantService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        flowforge_client: FlowForgeAPIClient,
        timeout_seconds: float = settings.assistant_graph_timeout_seconds,
        recursion_limit: int = settings.assistant_graph_recursion_limit,
        agent: RunnableAgent | None = None,
        conversation_repository: ConversationRepository | None = None,
    ) -> None:
        self._session = session
        self._embedding_provider = embedding_provider
        self._flowforge_client = flowforge_client
        self._timeout_seconds = timeout_seconds
        self._recursion_limit = recursion_limit
        self._agent = agent
        self._conversation_repository = (
            conversation_repository or AssistantConversationRepository(session)
        )

    async def query(
        self,
        *,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        question: str,
        thread_id: str | None = None,
        allow_write_tools: bool = False,
    ) -> ProjectAssistantQueryResponse:
        resolved_thread_id = thread_id or str(uuid.uuid4())
        await self._conversation_repository.ensure_thread(
            thread_id=resolved_thread_id,
            organization_id=organization_id,
            project_id=project_id,
            user_id=user_id,
        )
        previous_messages = await self._conversation_repository.list_messages(
            thread_id=resolved_thread_id,
            limit=20,
        )
        await self._conversation_repository.add_message(
            thread_id=resolved_thread_id,
            role="user",
            content=question,
        )

        agent = self._agent or create_project_agent(
            tools=[
                create_search_project_knowledge_tool(
                    session=self._session,
                    embedding_provider=self._embedding_provider,
                    organization_id=organization_id,
                    project_id=project_id,
                ),
                *create_flowforge_read_tools(client=self._flowforge_client),
                *create_flowforge_write_tools(
                    client=self._flowforge_client,
                    approved=allow_write_tools,
                    approval_repository=cast(
                        ApprovalRepository,
                        self._conversation_repository,
                    ),
                    thread_id=resolved_thread_id,
                    organization_id=organization_id,
                    project_context_id=project_id,
                    user_id=user_id,
                ),
            ]
        )

        try:
            result = await asyncio.wait_for(
                agent.ainvoke(
                    {
                        "messages": [
                            _context_message(
                                organization_id=organization_id,
                                project_id=project_id,
                                user_id=user_id,
                                allow_write_tools=allow_write_tools,
                            ),
                            *_langchain_messages(previous_messages),
                            HumanMessage(content=question),
                        ],
                    },
                    config={
                        "recursion_limit": self._recursion_limit,
                        "configurable": {
                            "thread_id": resolved_thread_id,
                        },
                    },
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise ProjectAssistantTimeoutError("Project agent timed out") from exc
        except Exception as exc:
            raise ProjectAssistantExecutionError(
                "Project agent execution failed"
            ) from exc

        answer = _last_message_content(result)
        await self._conversation_repository.add_message(
            thread_id=resolved_thread_id,
            role="assistant",
            content=answer,
            metadata={
                "write_tools_enabled": allow_write_tools,
            },
        )
        if isinstance(self._session, AsyncSession):
            await self._session.commit()

        return ProjectAssistantQueryResponse(
            answer=answer,
            thread_id=resolved_thread_id,
            write_tools_enabled=allow_write_tools,
        )


def _context_message(
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    allow_write_tools: bool,
) -> SystemMessage:
    write_tool_policy = (
        "Write tools are enabled only after explicit approval."
        if allow_write_tools
        else "Write tools must request human approval and must not mutate data."
    )
    return SystemMessage(
        content=(
            "You are the FlowForge Project Agent. Use the current authenticated "
            "context for tool calls unless the user explicitly asks for another "
            "accessible entity.\n"
            f"organization_id: {organization_id}\n"
            f"project_id: {project_id}\n"
            f"user_id: {user_id}\n"
            f"{write_tool_policy}\n"
            "For project-scoped task questions, call list_tasks with the current "
            "project_id. For project details, call get_project with the current "
            "project_id. Keep answers concise and cite task/project ids when useful."
        )
    )


def _last_message_content(result: Mapping[str, Any]) -> str:
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return ""

    content = getattr(messages[-1], "content", "")
    if isinstance(content, str):
        return content

    return str(content)


def _langchain_messages(messages: list[Any]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []

    for message in messages:
        if message.role == "user":
            converted.append(HumanMessage(content=message.content))
        elif message.role == "assistant":
            converted.append(AIMessage(content=message.content))

    return converted
