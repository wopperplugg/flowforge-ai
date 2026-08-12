import uuid

from langchain_core.documents import Document
from sqlalchemy.ext.asyncio import AsyncSession

from src.embeddings.base import EmbeddingProvider
from src.knowledge.repository import KnowledgeRepository


async def retrieve_documents(
        *,
        query: str,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        limit: int = 5,
) -> list[Document]:
    embedding = await embedding_provider.embed_text(query)

    repository = KnowledgeRepository(session)

    chunks = await repository.search_similar(
        organization_id=organization_id,
        project_id=project_id,
        embedding=embedding,
        limit=limit,
    )

    return [
        Document(
            page_content=chunk.content,
            metadata={
                "source_id": str(chunk.source_id),
                "chunk_index": chunk.chunk_index,
            },
        )
        for chunk in chunks
    ]