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
                "source_type": chunk.source.source_type,
                "source_entity_id": (
                    str(chunk.source.source_entity_id)
                    if chunk.source.source_entity_id is not None
                    else None
                ),
                "source_title": chunk.source.title,
                "source_metadata": chunk.source.source_metadata,
                "organization_id": str(chunk.organization_id),
                "project_id": (
                    str(chunk.project_id) if chunk.project_id is not None else None
                ),
                "chunk_index": chunk.chunk_index,
            },
        )
        for chunk in chunks
    ]
