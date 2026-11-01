from abc import ABC, abstractmethod
from typing import Any


class MessageBroker(ABC):
    @abstractmethod
    async def send(
        self,
        payload: dict[str, Any],
        trace_id: str | None = None,
    ) -> None: ...
