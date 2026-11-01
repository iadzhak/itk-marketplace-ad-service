from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.outbox import OutboxMessage, OutboxRepository
from src.infrastructure.persistence.models import OutboxModel
from src.infrastructure.tracing import get_trace_id


class SQLAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event_type: str, payload: dict[str, Any]) -> None:
        self._session.add(
            OutboxModel(
                event_type=event_type,
                payload=payload,
                trace_id=get_trace_id(),
            )
        )

    async def fetch_unpublished(self, limit: int) -> list[OutboxMessage]:
        stmt = (
            select(OutboxModel)
            .where(OutboxModel.published_at.is_(None))
            .order_by(OutboxModel.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            OutboxMessage(
                id=m.id,
                event_type=m.event_type,
                payload=m.payload,
                trace_id=m.trace_id,
            )
            for m in models
        ]

    async def mark_published(self, ids: list[int]) -> None:
        if not ids:
            return
        await self._session.execute(
            update(OutboxModel)
            .where(OutboxModel.id.in_(ids))
            .values(published_at=func.now())
        )
