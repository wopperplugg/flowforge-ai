import hashlib
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.embeddings.base import EmbeddingProvider
from src.ingestion.chunker import TextChunker
from src.ingestion.schemas import IndexSourceCommand
from src.knowledge.models import (
    KnowledgeChunk,
    KnowledgeSource,
)
from src.knowledge.repository import KnowledgeRepository


class IngestionService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider,
        chunker: TextChunker,
    ) -> None:
        self._session = session
        self._repository = KnowledgeRepository(session)
        self._embedding_provider = embedding_provider
        self._chunker = chunker

    async def index_source(
        self,
        command: IndexSourceCommand,
    ) -> KnowledgeSource:
        normalized_content = " ".join(command.content.split())

        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

        existing_source = None

        if command.source_entity_id is not None:
            existing_source = await self._repository.get_source(
                organization_id=command.organization_id,
                source_type=command.source_type,
                source_entity_id=command.source_entity_id,
            )

        if existing_source is not None and existing_source.content_hash == content_hash:
            existing_source.project_id = command.project_id
            existing_source.title = command.title
            existing_source.raw_content = normalized_content
            existing_source.source_metadata = command.metadata
            existing_source.source_version = command.source_version

            await self._session.flush()
            return existing_source

        text_chunks = self._chunker.split(normalized_content)

        if not text_chunks:
            raise ValueError("Source content produced no chunks")

        texts = [chunk.content for chunk in text_chunks]

        embeddings = await self._embedding_provider.embed_documents(texts)

        if len(embeddings) != len(text_chunks):
            raise RuntimeError(
                "Embedding provider returned unexpected number of vectors"
            )

        if existing_source is None:
            source = KnowledgeSource(
                organization_id=command.organization_id,
                project_id=command.project_id,
                source_type=command.source_type,
                source_entity_id=command.source_entity_id,
                title=command.title,
                raw_content=normalized_content,
                source_metadata=command.metadata,
                content_hash=content_hash,
                source_version=command.source_version,
                embedding_model=self._embedding_provider.model_name,
                last_indexed_at=datetime.now(UTC),
            )

            await self._repository.add_source(source)
        else:
            source = existing_source

            source.project_id = command.project_id
            source.title = command.title
            source.raw_content = normalized_content
            source.source_metadata = command.metadata
            source.content_hash = content_hash
            source.source_version = command.source_version
            source.embedding_model = self._embedding_provider.model_name
            source.last_indexed_at = datetime.now(UTC)

            await self._repository.delete_chunks(source_id=source.id)

        chunks = [
            KnowledgeChunk(
                source_id=source.id,
                organization_id=command.organization_id,
                project_id=command.project_id,
                chunk_index=text_chunk.index,
                content=text_chunk.content,
                content_hash=hashlib.sha256(
                    text_chunk.content.encode("utf-8")
                ).hexdigest(),
                embedding=embedding,
            )
            for text_chunk, embedding in zip(
                text_chunks,
                embeddings,
                strict=True,
            )
        ]

        await self._repository.add_chunks(chunks)

        return source
