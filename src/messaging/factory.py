from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.embeddings.ollama import OllamaEmbeddingProvider
from src.ingestion.chunker import TextChunker
from src.ingestion.service import IngestionService


def create_ingestion_service(
    session: AsyncSession,
) -> IngestionService:
    embedding_provider = OllamaEmbeddingProvider(
        base_url=settings.ollama_base_url,
        model=settings.embedding_model,
    )

    chunker = TextChunker(
        chunk_size=1000,
        chunk_overlap=200,
    )

    return IngestionService(
        session=session,
        embedding_provider=embedding_provider,
        chunker=chunker,
    )
