import asyncio
import uuid

import pytest
from langchain_core.documents import Document

from src.agents.rag.service import AssistantTimeoutError, RAGAssistantService


class FakeEmbeddingProvider:
    model_name = "test-embedding"

    async def embed_text(self, query: str) -> list[float]:
        return [0.1, 0.2]


class FakeGraph:
    def __init__(self) -> None:
        self.config = None

    async def ainvoke(self, input, config=None):
        self.config = config
        return {
            "answer": "Answer [source:1]",
            "query": "rewritten query",
            "rewrite_count": 1,
            "documents_relevant": True,
            "documents": [
                Document(
                    page_content="content",
                    metadata={
                        "source_id": str(uuid.uuid4()),
                        "source_type": "task",
                        "source_entity_id": str(uuid.uuid4()),
                        "source_title": "Task title",
                        "source_metadata": {"url": "https://flowforge.local/task/1"},
                        "chunk_index": 2,
                    },
                )
            ],
        }


class FakeConversationRepository:
    def __init__(self) -> None:
        self.messages = []

    async def ensure_thread(self, **kwargs):
        self.thread = kwargs

    async def add_message(self, **kwargs):
        self.messages.append(kwargs)


async def test_rag_assistant_service_returns_structured_response() -> None:
    graph = FakeGraph()
    conversation_repository = FakeConversationRepository()
    service = RAGAssistantService(
        session=object(),
        embedding_provider=FakeEmbeddingProvider(),
        timeout_seconds=1,
        recursion_limit=8,
        graph=graph,
        conversation_repository=conversation_repository,
    )

    response = await service.query(
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        question="How does auth work?",
        thread_id="thread-1",
    )

    assert response.answer == "Answer [source:1]"
    assert response.thread_id == "thread-1"
    assert response.query == "rewritten query"
    assert response.rewrite_count == 1
    assert response.documents_relevant is True
    assert response.sources[0].source_type == "task"
    assert response.sources[0].source_title == "Task title"
    assert response.sources[0].chunk_index == 2
    assert response.sources[0].url == "https://flowforge.local/task/1"
    assert graph.config == {
        "recursion_limit": 8,
        "configurable": {
            "thread_id": "thread-1",
        },
    }
    assert [message["role"] for message in conversation_repository.messages] == [
        "user",
        "assistant",
    ]


async def test_rag_assistant_service_generates_thread_id_when_missing() -> None:
    service = RAGAssistantService(
        session=object(),
        embedding_provider=FakeEmbeddingProvider(),
        timeout_seconds=1,
        graph=FakeGraph(),
        conversation_repository=FakeConversationRepository(),
    )

    response = await service.query(
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        question="How does auth work?",
    )

    assert uuid.UUID(response.thread_id)


async def test_rag_assistant_service_raises_timeout() -> None:
    class SlowGraph:
        async def ainvoke(self, input, config=None):
            await asyncio.sleep(1)

    service = RAGAssistantService(
        session=object(),
        embedding_provider=FakeEmbeddingProvider(),
        timeout_seconds=0.001,
        graph=SlowGraph(),
        conversation_repository=FakeConversationRepository(),
    )

    with pytest.raises(AssistantTimeoutError):
        await service.query(
            organization_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            question="How does auth work?",
        )
