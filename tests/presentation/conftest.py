from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.infrastructure.tracing import TraceIdMiddleware
from src.presentation.api.dependencies import (
    get_settings,
    get_uow,
    get_user_profile_service,
)
from src.presentation.api.routes.internal import router as internal_router
from src.presentation.api.routes.public import router as public_router
from src.settings import Settings
from tests.conftest import FakeUnitOfWork, FakeUserProfileService

JWT_SECRET = "test-secret-key-that-is-long-enough"
JWT_ALGORITHM = "HS256"

_test_settings = Settings(
    database_url="postgresql+asyncpg://fake:fake@localhost/fake",
    jwt_secret=JWT_SECRET,
    jwt_algorithm=JWT_ALGORITHM,
    kafka_bootstrap_servers="localhost:9092",
    kafka_topic_ads="ads",
)


@pytest.fixture
def app(
    fake_uow: FakeUnitOfWork,
    fake_user_profile: FakeUserProfileService,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)
    app.include_router(public_router)
    app.include_router(internal_router)

    app.dependency_overrides[get_uow] = lambda: fake_uow
    app.dependency_overrides[get_settings] = lambda: _test_settings
    app.dependency_overrides[get_user_profile_service] = lambda: fake_user_profile

    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def make_access_token(user_id: int, email: str = "user@test.com") -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_access_token(user_id=1)}"}


@pytest.fixture
def other_auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_access_token(user_id=2)}"}
