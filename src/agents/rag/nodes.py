import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

from langchain_core.documents import Document
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.model import create_chat_model
from src.agents.rag.retrieval import retrieve_documents
from src.agents.rag.state import RAGState
from src.embeddings.base import EmbeddingProvider

MAX_RETRIEVAL_REQUESTS = 2
SOURCE_URL_METADATA_KEYS = ("url", "source_url", "web_url", "link")
RAGNode = Callable[[RAGState], Awaitable[dict[str, Any]]]


class DocumentGrade(BaseModel):
    relevant: bool = Field(
        description="Whether the retrieved documents are relevant to the user query."
    )


def _source_url(metadata: Mapping[str, Any]) -> str | None:
    source_metadata = metadata.get("source_metadata")

    if not isinstance(source_metadata, Mapping):
        return None

    for key in SOURCE_URL_METADATA_KEYS:
        value = source_metadata.get(key)
        if isinstance(value, str) and value:
            return value

    return None


def _source_reference(index: int, document: Document) -> str:
    metadata = document.metadata
    title = metadata.get("source_title") or "Untitled source"
    source_type = metadata.get("source_type") or "source"
    source_entity_id = metadata.get("source_entity_id") or "unknown"
    chunk_index = metadata.get("chunk_index")
    url = _source_url(metadata)

    parts = [
        f"[source:{index}]",
        str(title),
        f"type={source_type}",
        f"entity_id={source_entity_id}",
    ]

    if chunk_index is not None:
        parts.append(f"chunk={chunk_index}")

    if url is not None:
        parts.append(f"url={url}")

    return " | ".join(parts)


def _format_context_document(index: int, document: Document) -> str:
    return f"{_source_reference(index, document)}\n{document.page_content}"


def _format_sources(documents: list[Document]) -> str:
    if not documents:
        return ""

    references = [
        _source_reference(index, document)
        for index, document in enumerate(
            documents,
            start=1,
        )
    ]

    return "Sources:\n" + "\n".join(f"- {reference}" for reference in references)


def create_retrieve_node(
    *,
    session: AsyncSession,
    embedding_provider: EmbeddingProvider,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
) -> RAGNode:
    async def retrieve(state: RAGState) -> dict[str, Any]:
        documents = await retrieve_documents(
            query=state["query"],
            session=session,
            embedding_provider=embedding_provider,
            organization_id=organization_id,
            project_id=project_id,
        )

        return {
            "documents": documents,
        }

    return retrieve


def route_after_grading(state: RAGState) -> str:
    if state["documents_relevant"]:
        return "generate"

    if state["rewrite_count"] < MAX_RETRIEVAL_REQUESTS - 1:
        return "rewrite_query"

    return "fallback"


async def fallback(state: RAGState) -> dict[str, Any]:
    return {
        "answer": (
            "I could not find enough relevant information "
            "in the current project knowledge to answer this question."
        )
    }


def create_grade_documents_node() -> RAGNode:
    model = create_chat_model()

    grader = model.with_structured_output(DocumentGrade)

    async def grade_documents(state: RAGState) -> dict[str, Any]:
        query = state["query"]
        documents = state["documents"]

        if not documents:
            return {
                "documents_relevant": False,
            }

        relevant_documents: list[Document] = []

        for index, document in enumerate(
            documents,
            start=1,
        ):
            result = cast(
                DocumentGrade,
                await grader.ainvoke(
                    [
                        {
                            "role": "system",
                            "content": (
                                "You are a relevance grader. "
                                "Determine whether this single retrieved project "
                                "document contains information useful for answering "
                                "the user's query."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Query:\n{query}\n\n"
                                f"Retrieved document:\n"
                                f"{_format_context_document(index, document)}"
                            ),
                        },
                    ]
                ),
            )

            if result.relevant:
                relevant_documents.append(document)

        return {
            "documents": relevant_documents,
            "documents_relevant": bool(relevant_documents),
        }

    return grade_documents


def create_generate_node() -> RAGNode:
    model = create_chat_model()

    async def generate(state: RAGState) -> dict[str, Any]:
        query = state["query"]
        documents = state["documents"]

        context = "\n\n".join(
            _format_context_document(index, document)
            for index, document in enumerate(
                documents,
                start=1,
            )
        )

        response = await model.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You are the FlowForge project assistant. "
                        "Answer the user's question using only the provided "
                        "project context. "
                        "Do not invent project facts. "
                        "If the context is insufficient, say so explicitly. "
                        "Cite sources inline using the [source:N] references "
                        "from the provided context."
                    ),
                },
                {
                    "role": "user",
                    "content": (f"Question:\n{query}\n\nProject context:\n{context}"),
                },
            ]
        )

        answer = str(response.content)
        sources = _format_sources(documents)

        if sources:
            answer = f"{answer}\n\n{sources}"

        return {
            "answer": answer,
        }

    return generate


def create_rewrite_query_node() -> RAGNode:
    model = create_chat_model()

    async def rewrite_query(state: RAGState) -> dict[str, Any]:
        query = state["query"]

        response = await model.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You rewrite search queries for semantic retrieval. "
                        "Rewrite the user's query so that it is more likely "
                        "to retrieve relevant project documentation. "
                        "Return only the rewritten query."
                    ),
                },
                {
                    "role": "user",
                    "content": query,
                },
            ]
        )

        return {
            "query": str(response.content).strip(),
            "rewrite_count": state["rewrite_count"] + 1,
        }

    return rewrite_query
