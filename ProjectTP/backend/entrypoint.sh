#!/usr/bin/env sh
set -eu

# Без секрета сессии Starlette падает; uvicorn не слушает порт → healthcheck unhealthy.
if [ -z "${SESSION_SECRET:-}" ]; then
  echo "FATAL: SESSION_SECRET пустой или не задан. В ProjectTP/.env задайте непустую строку, например:" >&2
  echo "  openssl rand -hex 32" >&2
  exit 1
fi

PORT="${PORT:-8000}"

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
