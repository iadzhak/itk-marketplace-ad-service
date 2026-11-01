from datetime import UTC, datetime
from types import TracebackType
from typing import Any, List

import pytest

from src.application.ports.message_broker import MessageBroker
from src.application.ports.outbox import OutboxMessage, OutboxRepository
from src.application.ports.repositories import AdRepository
from src.application.ports.uow import UnitOfWork
from src.application.ports.user_profile import UserInfo, UserProfileService
from src.infrastructure.tracing import get_trace_id
from src.domain.entities import Ad, AdStatus


class FakeAdRepository(AdRepository):
    def __init__(self) -> None:
        self._ads: dict[int, Ad] = {}
        self._next_id = 1

    async def create(
        self,
        user_id: int,
        title: str,
        description: str,
        price: int,
        category: str,
        city: str,
    ) -> Ad:
        now = datetime.now(UTC)
        ad = Ad(
            id=self._next_id,
            user_id=user_id,
            title=title,
            description=description,
            price=price,
            category=category,
            city=city,
            status=AdStatus.ACTIVE,
            views=0,
            created_at=now,
            updated_at=now,
        )
        self._ads[ad.id] = ad
        self._next_id += 1
        return ad

    async def get_by_id(self, ad_id: int) -> Ad | None:
        return self._ads.get(ad_id)

    async def list(
        self,
        user_id: int | None,
        limit: int,
        offset: int,
    ) -> tuple[List[Ad], int]:
        filtered = [ad for ad in self._ads.values() if ad.status == AdStatus.ACTIVE]
        if user_id is not None:
            filtered = [ad for ad in filtered if ad.user_id == user_id]

        filtered.sort(key=lambda a: a.created_at, reverse=True)

        return filtered[offset : offset + limit], len(filtered)

    async def save(self, ad: Ad) -> None:
        self._ads[ad.id] = ad


class FakeOutboxRepository(OutboxRepository):
    def __init__(self) -> None:
        self.messages: list[OutboxMessage] = []
        self._next_id = 1

    async def add(self, event_type: str, payload: dict[str, Any]) -> None:
        self.messages.append(
            OutboxMessage(
                id=self._next_id,
                event_type=event_type,
                payload=payload,
                trace_id=get_trace_id(),
            )
        )
        self._next_id += 1

    async def fetch_unpublished(self, limit: int) -> list[OutboxMessage]:
        return self.messages[:limit]

    async def mark_published(self, ids: list[int]) -> None:
        self.messages = [m for m in self.messages if m.id not in ids]


class FakeMessageBroker(MessageBroker):
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.sent_trace_ids: list[str | None] = []
        self.logged_trace_ids: list[str | None] = []

    async def send(
        self, payload: dict[str, Any], trace_id: str | None = None
    ) -> None:
        self.sent.append(payload)
        self.sent_trace_ids.append(trace_id)
        self.logged_trace_ids.append(get_trace_id())


class FakeUserProfileService(UserProfileService):
    def __init__(self, names: dict[int, str] | None = None) -> None:
        self.names: dict[int, str] = names or {}
        self.calls: list[int] = []

    async def user(self, user_id: int) -> UserInfo | None:
        self.calls.append(user_id)
        name = self.names.get(user_id)
        if name is None:
            return None
        return UserInfo(id=user_id, name=name)


class FakeUnitOfWork(UnitOfWork):
    def __init__(
        self,
        ad_repo: FakeAdRepository | None = None,
        outbox_repo: FakeOutboxRepository | None = None,
    ) -> None:
        self.ads = ad_repo or FakeAdRepository()
        self.outbox = outbox_repo or FakeOutboxRepository()
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()


@pytest.fixture
def fake_ad_repo() -> FakeAdRepository:
    return FakeAdRepository()


@pytest.fixture
def fake_outbox_repo() -> FakeOutboxRepository:
    return FakeOutboxRepository()


@pytest.fixture
def fake_uow(
    fake_ad_repo: FakeAdRepository,
    fake_outbox_repo: FakeOutboxRepository,
) -> FakeUnitOfWork:
    return FakeUnitOfWork(fake_ad_repo, fake_outbox_repo)


@pytest.fixture
def fake_broker() -> FakeMessageBroker:
    return FakeMessageBroker()


@pytest.fixture
def fake_user_profile() -> FakeUserProfileService:
    return FakeUserProfileService({1: "Alice", 2: "Bob"})
