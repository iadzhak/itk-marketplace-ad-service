from typing import Any

import httpx

from src.infrastructure.tracing import TRACE_ID_HEADER, trace_context
from src.infrastructure.messaging.kafka_broker import KafkaMessageBroker
from src.infrastructure.http.trace_hook import inject_trace_id


class FakeProducer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], Any]] = []

    async def send_and_wait(
        self, topic: str, value: dict[str, Any], headers: Any = None
    ) -> None:
        self.calls.append((topic, value, headers))


async def _request_headers(inside_context: bool) -> httpx.Headers:
    captured: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers)
        return httpx.Response(200)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        event_hooks={"request": [inject_trace_id]},
    ) as client:
        if inside_context:
            with trace_context("trace-http"):
                await client.get("http://auth/internal/users/1")
        else:
            await client.get("http://auth/internal/users/1")
    return captured[0]


async def test_http_hook_adds_trace_id_header() -> None:
    headers = await _request_headers(inside_context=True)

    assert headers[TRACE_ID_HEADER] == "trace-http"


async def test_http_hook_skips_header_without_trace_id() -> None:
    headers = await _request_headers(inside_context=False)

    assert TRACE_ID_HEADER not in headers


async def test_kafka_broker_sends_trace_id_header() -> None:
    producer = FakeProducer()
    broker = KafkaMessageBroker(producer=producer, topic="ads")

    await broker.send({"event": "ad.created"}, trace_id="trace-k")

    assert producer.calls == [
        ("ads", {"event": "ad.created"}, [("x-trace-id", b"trace-k")])
    ]


async def test_kafka_broker_omits_headers_without_trace_id() -> None:
    producer = FakeProducer()
    broker = KafkaMessageBroker(producer=producer, topic="ads")

    await broker.send({"event": "ad.created"})

    assert producer.calls == [("ads", {"event": "ad.created"}, None)]
