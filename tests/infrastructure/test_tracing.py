import logging

from src.infrastructure.tracing import (
    reset_trace_id,
    resolve_trace_id,
    set_trace_id,
)
from src.infrastructure.tracing import NO_TRACE_ID, setup_logging


def test_resolve_keeps_valid_value() -> None:
    assert resolve_trace_id("req_42-A") == "req_42-A"


def test_resolve_generates_for_none_and_empty() -> None:
    assert resolve_trace_id(None) != resolve_trace_id(None)
    assert len(resolve_trace_id("")) == 36


def test_log_record_has_trace_id_inside_context() -> None:
    setup_logging()
    token = set_trace_id("ctx-1")
    try:
        record = logging.getLogger("t").makeRecord("t", logging.INFO, "f", 1, "m", (), None)
    finally:
        reset_trace_id(token)

    assert record.trace_id == "ctx-1"


def test_log_record_has_placeholder_outside_context() -> None:
    setup_logging()

    record = logging.getLogger("t").makeRecord("t", logging.INFO, "f", 1, "m", (), None)

    assert record.trace_id == NO_TRACE_ID


def test_setup_logging_is_idempotent() -> None:
    root = logging.getLogger()
    setup_logging()
    handlers_after_first = len(root.handlers)

    setup_logging()

    assert len(root.handlers) == handlers_after_first
