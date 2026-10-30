#!/bin/bash

set -e

uv run alembic upgrade head

set -m

uv run uvicorn bin.api:app --host 0.0.0.0 --port 8000 &
pid1=$!

uv run python -m bin.outbox &
pid2=$!

trap "kill $pid1 $pid2 2>/dev/null; exit 1" INT TERM

wait "$pid1"
wait "$pid2"