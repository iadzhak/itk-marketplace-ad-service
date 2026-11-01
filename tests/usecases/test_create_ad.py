import pytest

from src.infrastructure.tracing import trace_context
from src.application.usecases.create_ad import CreateAd
from tests.conftest import FakeUnitOfWork


@pytest.mark.asyncio
async def test_create_ad_persists_and_writes_outbox(fake_uow: FakeUnitOfWork) -> None:
    usecase = CreateAd(fake_uow)

    ad = await usecase.execute(
        user_id=1,
        title="MacBook Pro",
        description="16 inch",
        price=120000,
        category="Электроника",
        city="Москва",
    )

    assert ad.id == 1
    assert ad.user_id == 1
    assert ad.status.value == "active"
    assert fake_uow.committed

    assert len(fake_uow.outbox.messages) == 1
    message = fake_uow.outbox.messages[0]
    assert message.event_type == "ad.created"
    assert message.payload == {"ad_id": 1}


@pytest.mark.asyncio
async def test_create_ad_stores_current_trace_id_in_outbox(
    fake_uow: FakeUnitOfWork,
) -> None:
    usecase = CreateAd(fake_uow)

    with trace_context("trace-create"):
        await usecase.execute(
            user_id=1,
            title="MacBook Pro",
            description="16 inch",
            price=120000,
            category="Электроника",
            city="Москва",
        )

    assert fake_uow.outbox.messages[0].trace_id == "trace-create"
