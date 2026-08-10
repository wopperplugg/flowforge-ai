import uuid

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge.models import KnowledgeChunk, KnowledgeSource


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_source(
            self,
            source: KnowledgeSource,
    ) -> KnowledgeSource:
        self._session.add(source)
        await self._session.flush()
        return source

    async def add_chunks(
            self,
            chunks: list[KnowledgeChunk],
    ) -> None:
        self._session.add_all(chunks)
        await self._session.flush()

    async def search_similar(
            self,
            *,
            organization_id: uuid.UUID,
            embedding: list[float],
            limit: int = 5,
            project_id: uuid.UUID | None = None,
    ) -> list[KnowledgeChunk]:
        query: Select[tuple[KnowledgeChunk]] = (
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.organization_id == organization_id,
            )
            .order_by(
                KnowledgeChunk.embedding.cosine_distance(embedding),
            )
            .limit(limit)
        )

        if project_id is not None:
            query = query.where(
                KnowledgeChunk.project_id == project_id,
            )

        result = await self._session.scalars(query)

        return list(result.all())

    async def get_source(
        self,
        *,
        organization_id: uuid.UUID,
        source_type: str,
        source_entity_id: uuid.UUID,
    ) -> KnowledgeSource | None:
        query = select(KnowledgeSource).where(
            KnowledgeSource.organization_id == organization_id,
            KnowledgeSource.source_type == source_type,
            KnowledgeSource.source_entity_id == source_entity_id,
        )

        result = await self._session.scalar(query)

        return result

    async def delete_chunks(
            self,
            *,
            source_id: uuid.UUID,
    ) -> None:
        await self._session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.source_id == source_id,
            )
        )

    async def delete_source(
            self,
            *,
            organization_id: uuid.UUID,
            source_type: str,
            source_entity_id: uuid.UUID,
    ) -> int:
        result = await self._session.execute(
            delete(KnowledgeSource).where(
                KnowledgeSource.organization_id == organization_id,
                KnowledgeSource.source_type == source_type,
                KnowledgeSource.source_entity_id == source_entity_id,
            )
        )

        return result.rowcount or 0
