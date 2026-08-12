import asyncio
import uuid
from collections.abc import Mapping
from typing import Any, Protocol

from langchain_core.documents import Document
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.conversation_repository import AssistantConversationRepository
from src.agents.rag.graph import create_rag_graph
from src.agents.rag.nodes import (
    create_generate_node,
    create_grade_documents_node,
    create_retrieve_node,
    create_rewrite_query_node,
)
from src.agents.rag.schemas import AssistantQueryResponse, AssistantSource
from src.config import settings
from src.embeddings.base import EmbeddingProvider


class RunnableGraph(Protocol):
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

    async def add_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any: ...


class AssistantExecutionError(RuntimeError):
    pass


class AssistantTimeoutError(AssistantExecutionError):
    pass


class RAGAssistantService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        timeout_seconds: float = settings.assistant_graph_timeout_seconds,
        recursion_limit: int = settings.assistant_graph_recursion_limit,
        checkpointer: InMemorySaver | None = None,
        graph: RunnableGraph | None = None,
        conversation_repository: ConversationRepository | None = None,
    ) -> None:
        self._session = session
        self._embedding_provider = embedding_provider
        self._timeout_seconds = timeout_seconds
        self._recursion_limit = recursion_limit
        self._checkpointer = checkpointer
        self._graph = graph
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
    ) -> AssistantQueryResponse:
        resolved_thread_id = thread_id or str(uuid.uuid4())
        await self._conversation_repository.ensure_thread(
            thread_id=resolved_thread_id,
            organization_id=organization_id,
            project_id=project_id,
            user_id=user_id,
        )
        await self._conversation_repository.add_message(
            thread_id=resolved_thread_id,
            role="user",
            content=question,
        )
        graph = self._graph or create_rag_graph(
            retrieve_node=create_retrieve_node(
                session=self._session,
                embedding_provider=self._embedding_provider,
                organization_id=organization_id,
                project_id=project_id,
            ),
            grade_documents_node=create_grade_documents_node(),
            generate_node=create_generate_node(),
            rewrite_query_node=create_rewrite_query_node(),
            checkpointer=self._checkpointer,
        )

        try:
            result = await asyncio.wait_for(
                graph.ainvoke(
                    {
                        "messages": [],
                        "query": question,
                        "documents": [],
                        "documents_relevant": False,
                        "answer": "",
                        "rewrite_count": 0,
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
            raise AssistantTimeoutError("Assistant graph timed out") from exc
        except Exception as exc:
            raise AssistantExecutionError("Assistant graph execution failed") from exc

        response = AssistantQueryResponse(
            answer=str(result.get("answer") or ""),
            thread_id=resolved_thread_id,
            query=str(result.get("query") or question),
            rewrite_count=int(result.get("rewrite_count") or 0),
            documents_relevant=bool(result.get("documents_relevant")),
            sources=_source_responses(result.get("documents") or []),
        )
        await self._conversation_repository.add_message(
            thread_id=resolved_thread_id,
            role="assistant",
            content=response.answer,
            metadata={
                "query": response.query,
                "rewrite_count": response.rewrite_count,
                "documents_relevant": response.documents_relevant,
            },
        )
        if isinstance(self._session, AsyncSession):
            await self._session.commit()
        return response


def _source_responses(documents: list[Document]) -> list[AssistantSource]:
    return [
        AssistantSource(
            source_id=_uuid_or_none(document.metadata.get("source_id")),
            source_type=_str_or_none(document.metadata.get("source_type")),
            source_entity_id=_uuid_or_none(document.metadata.get("source_entity_id")),
            source_title=_str_or_none(document.metadata.get("source_title")),
            chunk_index=_int_or_none(document.metadata.get("chunk_index")),
            url=_source_url(document.metadata),
        )
        for document in documents
    ]


def _source_url(metadata: Mapping[str, Any]) -> str | None:
    source_metadata = metadata.get("source_metadata")

    if not isinstance(source_metadata, Mapping):
        return None

    for key in ("url", "source_url", "web_url", "link"):
        value = source_metadata.get(key)
        if isinstance(value, str) and value:
            return value

    return None


def _uuid_or_none(value: object) -> uuid.UUID | None:
    if value is None:
        return None

    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None

    return str(value)


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    if not isinstance(value, str):
        return None

    try:
        return int(value)
    except ValueError:
        return None
