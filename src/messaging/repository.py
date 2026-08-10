import uuid
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.contracts import OutboxMessage
from src.messaging.models import ProcessedMessageEvent


class ProcessedMessageRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def claim_event(
        self,
        event: OutboxMessage,
    ) -> bool:
        statement = (
            insert(ProcessedMessageEvent)
            .values(
                event_id=event.event_id,
                event_type=event.event_type,
                event_version=event.event_version,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                organization_id=event.organization_id,
            )
            .on_conflict_do_nothing(
                index_elements=[ProcessedMessageEvent.event_id],
            )
            .returning(ProcessedMessageEvent.event_id)
        )

        claimed_event_id = await self._session.scalar(statement)

        return claimed_event_id is not None

    async def get_latest_aggregate_version(
        self,
        *,
        organization_id: uuid.UUID | None,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        exclude_event_id: uuid.UUID | None = None,
    ) -> int | None:
        query = select(
            func.max(ProcessedMessageEvent.event_version),
        ).where(
            ProcessedMessageEvent.organization_id == organization_id,
            ProcessedMessageEvent.aggregate_type == aggregate_type,
            ProcessedMessageEvent.aggregate_id == aggregate_id,
        )

        if exclude_event_id is not None:
            query = query.where(
                ProcessedMessageEvent.event_id != exclude_event_id,
            )

        return cast(int | None, await self._session.scalar(query))
