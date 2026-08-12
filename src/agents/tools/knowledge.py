import uuid

from langchain.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from src.embeddings.base import EmbeddingProvider
from src.knowledge.repository import KnowledgeRepository


def create_search_project_knowledge_tool(
        *,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
):
    @tool
    async def search_project_knowledge(
        query: str,
    ) -> str:
        """Search for relevant information in the current FlowForge project."""

        embedding = await embedding_provider.embed_text(query)

        repository = KnowledgeRepository(session)

        chunks = await repository.search_similar(
            organization_id=organization_id,
            project_id=project_id,
            embedding=embedding,
            limit=5,
        )

        if not chunks:
            return "No relevant project information was found."

        return "\n\n".join(
            f"[Chunk {chunk.chunk_index}]\n{chunk.content}"
            for chunk in chunks
        )
    return search_project_knowledge