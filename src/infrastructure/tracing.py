import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from uvicorn.logging import AccessFormatter

TRACE_ID_HEADER = "X-Trace-Id"
NO_TRACE_ID = "-"

LOG_FORMAT = "%(asctime)s %(levelname)s [%(trace_id)s] %(name)s: %(message)s"
ACCESS_LOG_FORMAT = (
    "%(asctime)s %(levelname)s [%(trace_id)s] %(name)s: "
    '%(client_addr)s - "%(request_line)s" %(status_code)s'
)

_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HANDLER_MARKER = "_trace_id_handler"

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def new_trace_id() -> str:
    return str(uuid4())


def get_trace_id() -> str | None:
    return trace_id_var.get()


def set_trace_id(trace_id: str) -> Token:
    return trace_id_var.set(trace_id)


def reset_trace_id(token: Token) -> None:
    trace_id_var.reset(token)


def resolve_trace_id(raw: str | None) -> str:
    if raw is not None and _TRACE_ID_PATTERN.match(raw):
        return raw
    return new_trace_id()


@contextmanager
def trace_context(trace_id: str | None) -> Iterator[str]:
    resolved = resolve_trace_id(trace_id)
    token = set_trace_id(resolved)
    try:
        yield resolved
    finally:
        reset_trace_id(token)


class TraceIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        raw = MutableHeaders(scope=scope).get(TRACE_ID_HEADER)
        trace_id = resolve_trace_id(raw)
        token = set_trace_id(trace_id)

        async def send_with_trace_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[TRACE_ID_HEADER] = trace_id
            await send(message)

        try:
            await self._app(scope, receive, send_with_trace_id)
        finally:
            reset_trace_id(token)


def _install_record_factory() -> None:
    current = logging.getLogRecordFactory()
    if getattr(current, "_adds_trace_id", False):
        return

    def factory(*args, **kwargs) -> logging.LogRecord:
        record = current(*args, **kwargs)
        record.trace_id = get_trace_id() or NO_TRACE_ID
        return record

    factory._adds_trace_id = True
    logging.setLogRecordFactory(factory)


def _install_root_handler(level: str) -> None:
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not getattr(h, _HANDLER_MARKER, False)]
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    setattr(handler, _HANDLER_MARKER, True)
    root.addHandler(handler)
    root.setLevel(level)


def _patch_uvicorn_loggers() -> None:
    plain = logging.Formatter(LOG_FORMAT)
    access = AccessFormatter(fmt=ACCESS_LOG_FORMAT, use_colors=False)
    for name, formatter in (
        ("uvicorn", plain),
        ("uvicorn.error", plain),
        ("uvicorn.access", access),
    ):
        for handler in logging.getLogger(name).handlers:
            handler.setFormatter(formatter)


def setup_logging(level: str = "INFO") -> None:
    _install_record_factory()
    _install_root_handler(level)
    _patch_uvicorn_loggers()
