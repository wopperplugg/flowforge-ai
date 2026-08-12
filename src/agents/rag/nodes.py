import uuid

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.model import create_chat_model
from src.agents.rag.retrieval import retrieve_documents
from src.agents.rag.state import RAGState
from src.embeddings.base import EmbeddingProvider

MAX_RETRIEVAL_REQUESTS = 2


class DocumentGrade(BaseModel):
    relevant: bool = Field(
        description="Whether the retrieved documents are relevant to the user query."
    )


def create_retrieve_node(
    *,
    session: AsyncSession,
    embedding_provider: EmbeddingProvider,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
):
    async def retrieve(state: RAGState) -> dict:
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


async def fallback(state: RAGState) -> dict:
    return {
        "answer": (
            "I could not find enough relevant information "
            "in the current project knowledge to answer this question."
        )
    }


def create_grade_documents_node():
    model = create_chat_model()

    grader = model.with_structured_output(DocumentGrade)

    async def grade_documents(state: RAGState) -> dict:
        query = state["query"]
        documents = state["documents"]

        if not documents:
            return {
                "documents_relevant": False,
            }

        context = "\n\n".join(document.page_content for document in documents)

        result = await grader.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a relevance grader. "
                        "Determine whether the retrieved project documents "
                        "contain information useful for answering the user's query."
                    ),
                },
                {
                    "role": "user",
                    "content": (f"Query:\n{query}\n\nRetrieved documents:\n{context}"),
                },
            ]
        )

        return {
            "documents_relevant": result.relevant,
        }

    return grade_documents


def create_generate_node():
    model = create_chat_model()

    async def generate(state: RAGState) -> dict:
        query = state["query"]
        documents = state["documents"]

        context = "\n\n".join(document.page_content for document in documents)

        response = await model.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "You are the FlowForge project assistant. "
                        "Answer the user's question using only the provided "
                        "project context. "
                        "Do not invent project facts. "
                        "If the context is insufficient, say so explicitly."
                    ),
                },
                {
                    "role": "user",
                    "content": (f"Question:\n{query}\n\nProject context:\n{context}"),
                },
            ]
        )

        return {
            "answer": str(response.content),
        }

    return generate


def create_rewrite_query_node():
    model = create_chat_model()

    async def rewrite_query(state: RAGState) -> dict:
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
