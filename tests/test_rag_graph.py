from langchain_core.documents import Document

import src.agents.rag.graph as graph_module
import src.agents.rag.nodes as nodes_module
from src.agents.rag.graph import create_rag_graph
from src.agents.rag.nodes import route_after_grading


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
