import logging
import re

from httpx import AsyncClient

from src.infrastructure.tracing import TRACE_ID_HEADER, get_trace_id

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
URL = "/internal/ads/999"


async def test_generates_trace_id_when_header_missing(client: AsyncClient) -> None:
    resp = await client.get(URL)

    assert UUID_PATTERN.match(resp.headers[TRACE_ID_HEADER])


async def test_echoes_incoming_trace_id(client: AsyncClient) -> None:
    resp = await client.get(URL, headers={TRACE_ID_HEADER: "abc-123"})

    assert resp.headers[TRACE_ID_HEADER] == "abc-123"


async def test_replaces_invalid_trace_id(client: AsyncClient) -> None:
    resp = await client.get(URL, headers={TRACE_ID_HEADER: "bad value\twith spaces"})

    assert UUID_PATTERN.match(resp.headers[TRACE_ID_HEADER])


async def test_replaces_too_long_trace_id(client: AsyncClient) -> None:
    resp = await client.get(URL, headers={TRACE_ID_HEADER: "a" * 65})

    assert UUID_PATTERN.match(resp.headers[TRACE_ID_HEADER])


async def test_trace_id_reset_after_request(client: AsyncClient) -> None:
    await client.get(URL, headers={TRACE_ID_HEADER: "abc-123"})

    assert get_trace_id() is None


async def test_create_ad_logs_and_outbox_carry_trace_id(
    client: AsyncClient, auth_headers: dict[str, str], fake_uow, caplog
) -> None:
    caplog.set_level(logging.INFO)

    resp = await client.post(
        "/ads",
        json={
            "title": "MacBook",
            "description": "16 inch",
            "price": 100,
            "category": "Электроника",
            "city": "Москва",
        },
        headers={**auth_headers, TRACE_ID_HEADER: "trace-ad-1"},
    )

    assert resp.status_code == 201
    records = [r for r in caplog.records if "ad created" in r.getMessage()]
    assert records[0].trace_id == "trace-ad-1"
    assert fake_uow.outbox.messages[0].trace_id == "trace-ad-1"
