from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class OutboxMessage:
    id: int
    event_type: str
    payload: dict[str, Any]
    trace_id: str | None = None


class OutboxRepository(ABC):
    @abstractmethod
    async def add(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None: ...

    @abstractmethod
    async def fetch_unpublished(
        self,
        limit: int,
    ) -> list[OutboxMessage]: ...

    @abstractmethod
    async def mark_published(
        self,
        ids: list[int],
    ) -> None: ...
