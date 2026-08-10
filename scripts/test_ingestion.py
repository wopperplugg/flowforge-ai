import asyncio
import uuid

from src.config import settings
from src.embeddings.ollama import OllamaEmbeddingProvider
from src.infrastructure.database.session import (
    async_session_factory,
)
from src.ingestion.chunker import TextChunker
from src.ingestion.schemas import IndexSourceCommand
from src.ingestion.service import IngestionService
from src.knowledge.repository import KnowledgeRepository


async def main() -> None:
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()

    provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )

    chunker = TextChunker(
        chunk_size=300,
        chunk_overlap=50,
    )

    async with async_session_factory() as session:
        service = IngestionService(
            session=session,
            embedding_provider=provider,
            chunker=chunker,
        )

        await service.index_source(
            IndexSourceCommand(
                organization_id=organization_id,
                project_id=project_id,
                source_type="task",
                source_entity_id=uuid.uuid4(),
                title="Authentication",
                content=(
                    "FlowForge uses JWT authentication. "
                    "Access tokens are short lived. "
                    "Refresh tokens are rotated after use. "
                    "Old refresh sessions are revoked. "
                    "This prevents reuse of compromised "
                    "refresh tokens."
                ),
            )
        )

        repository = KnowledgeRepository(session)

        question = "How are refresh tokens protected?"

        query_embedding = await provider.embed_text(question)

        results = await repository.search_similar(
            organization_id=organization_id,
            project_id=project_id,
            embedding=query_embedding,
            limit=3,
        )

        print("Question:", question)

        for chunk in results:
            print()
            print(chunk.content)


if __name__ == "__main__":
    asyncio.run(main())
