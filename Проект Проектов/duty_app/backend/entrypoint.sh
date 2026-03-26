#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"

mkdir -p "$(dirname "${DATABASE_PATH:-/data/app.sqlite}")" || true
mkdir -p "${EXPORTS_DIR:-/exports}" || true

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
