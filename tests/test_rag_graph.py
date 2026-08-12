import uuid
from types import SimpleNamespace

from langchain_core.documents import Document

import src.agents.rag.graph as graph_module
import src.agents.rag.nodes as nodes_module
import src.agents.rag.retrieval as retrieval_module
from src.agents.rag.graph import create_rag_graph
from src.agents.rag.nodes import (
    create_generate_node,
    create_grade_documents_node,
    route_after_grading,
)


def test_graph_uses_nodes_from_same_package() -> None:
    assert graph_module.fallback is nodes_module.fallback
    assert graph_module.route_after_grading is nodes_module.route_after_grading


def test_route_after_grading_generates_when_documents_are_relevant() -> None:
    assert (
        route_after_grading(
            {
                "documents_relevant": True,
                "rewrite_count": 0,
            }
        )
        == "generate"
    )


def test_route_after_grading_rewrites_only_before_second_request() -> None:
    assert (
        route_after_grading(
            {
                "documents_relevant": False,
                "rewrite_count": 0,
            }
        )
        == "rewrite_query"
    )

    assert (
        route_after_grading(
            {
                "documents_relevant": False,
                "rewrite_count": 1,
            }
        )
        == "fallback"
    )


async def test_retrieve_documents_includes_source_metadata(
    monkeypatch,
) -> None:
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()
    source_entity_id = uuid.uuid4()

    class FakeEmbeddingProvider:
        async def embed_text(self, query: str) -> list[float]:
            return [0.1, 0.2]

    class FakeRepository:
        def __init__(self, session: object) -> None:
            self.session = session

        async def search_similar(self, **kwargs) -> list[object]:
            return [
                SimpleNamespace(
                    source_id=source_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    chunk_index=3,
                    content="Relevant chunk",
                    source=SimpleNamespace(
                        source_type="task",
                        source_entity_id=source_entity_id,
                        title="Task 42",
                        source_metadata={"url": "https://flowforge.local/tasks/42"},
                    ),
                )
            ]

    monkeypatch.setattr(
        retrieval_module,
        "KnowledgeRepository",
        FakeRepository,
    )

    documents = await retrieval_module.retrieve_documents(
        query="task",
        session=object(),
        embedding_provider=FakeEmbeddingProvider(),
        organization_id=organization_id,
        project_id=project_id,
    )

    assert documents[0].metadata == {
        "source_id": str(source_id),
        "source_type": "task",
        "source_entity_id": str(source_entity_id),
        "source_title": "Task 42",
        "source_metadata": {"url": "https://flowforge.local/tasks/42"},
        "organization_id": str(organization_id),
        "project_id": str(project_id),
        "chunk_index": 3,
    }


async def test_grade_documents_grades_and_filters_each_document(
    monkeypatch,
) -> None:
    calls: list[str] = []

    class FakeGrade:
        def __init__(self, relevant: bool) -> None:
            self.relevant = relevant

    class FakeGrader:
        async def ainvoke(self, messages: list[dict[str, str]]) -> FakeGrade:
            content = messages[-1]["content"]
            calls.append(content)
            return FakeGrade("Relevant chunk" in content)

    class FakeModel:
        def with_structured_output(self, schema: type) -> FakeGrader:
            return FakeGrader()

    monkeypatch.setattr(
        nodes_module,
        "create_chat_model",
        lambda: FakeModel(),
    )

    grade_documents = create_grade_documents_node()

    result = await grade_documents(
        {
            "query": "How does auth work?",
            "documents": [
                Document(page_content="Irrelevant chunk"),
                Document(page_content="Relevant chunk"),
            ],
        }
    )

    assert len(calls) == 2
    assert result["documents_relevant"] is True
    assert [document.page_content for document in result["documents"]] == [
        "Relevant chunk",
    ]


async def test_generate_answer_appends_sources(
    monkeypatch,
) -> None:
    class FakeResponse:
        content = "JWT is used for authentication [source:1]."

    class FakeModel:
        async def ainvoke(self, messages: list[dict[str, str]]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(
        nodes_module,
        "create_chat_model",
        lambda: FakeModel(),
    )

    generate = create_generate_node()

    result = await generate(
        {
            "query": "How does auth work?",
            "documents": [
                Document(
                    page_content="JWT authentication",
                    metadata={
                        "source_title": "Auth task",
                        "source_type": "task",
                        "source_entity_id": "task-1",
                        "source_metadata": {"url": "https://flowforge.local/tasks/1"},
                        "chunk_index": 0,
                    },
                )
            ],
        }
    )

    assert "Sources:" in result["answer"]
    assert "[source:1] | Auth task" in result["answer"]
    assert "url=https://flowforge.local/tasks/1" in result["answer"]


async def test_rag_graph_makes_at_most_two_retrieval_requests() -> None:
    retrieve_count = 0

    async def retrieve_node(state: dict) -> dict:
        nonlocal retrieve_count
        retrieve_count += 1
        return {
            "documents": [
                Document(page_content=f"Result for {state['query']}"),
            ],
        }

    async def grade_documents_node(state: dict) -> dict:
        return {
            "documents_relevant": False,
        }

    async def generate_node(state: dict) -> dict:
        return {
            "answer": "generated",
        }

    async def rewrite_query_node(state: dict) -> dict:
        return {
            "query": f"{state['query']} rewritten",
            "rewrite_count": state["rewrite_count"] + 1,
        }

    graph = create_rag_graph(
        retrieve_node=retrieve_node,
        grade_documents_node=grade_documents_node,
        generate_node=generate_node,
        rewrite_query_node=rewrite_query_node,
    )

    result = await graph.ainvoke(
        {
            "messages": [],
            "query": "How does deployment work?",
            "documents": [],
            "documents_relevant": False,
            "answer": "",
            "rewrite_count": 0,
        }
    )

    assert retrieve_count == 2
    assert result["answer"].startswith("I could not find enough relevant information")
    assert result["rewrite_count"] == 1
