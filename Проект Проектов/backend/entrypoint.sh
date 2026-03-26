#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"

# Run FastAPI app from backend/ directory.
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

