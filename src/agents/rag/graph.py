from langgraph.graph import END, START, StateGraph

from src.agents.rag.state import RAGState

from .nodes import fallback, route_after_grading


def create_rag_graph(
    *,
    retrieve_node,
    grade_documents_node,
    generate_node,
    rewrite_query_node,
):
    builder = StateGraph(RAGState)

    builder.add_node(
        "retrieve",
        retrieve_node,
    )

    builder.add_node(
        "grade_documents",
        grade_documents_node,
    )

    builder.add_node(
        "generate",
        generate_node,
    )

    builder.add_edge(
        START,
        "retrieve",
    )

    builder.add_edge(
        "retrieve",
        "grade_documents",
    )

    builder.add_node(
        "rewrite_query",
        rewrite_query_node,
    )

    builder.add_node(
        "fallback",
        fallback,
    )

    builder.add_conditional_edges(
        "grade_documents",
        route_after_grading,
        {
            "generate": "generate",
            "rewrite_query": "rewrite_query",
            "fallback": "fallback",
        },
    )

    builder.add_edge(
        "rewrite_query",
        "retrieve",
    )

    builder.add_edge(
        "generate",
        END,
    )

    builder.add_edge(
        "fallback",
        END,
    )

    return builder.compile()
