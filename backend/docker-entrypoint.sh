#!/bin/bash
set -e

echo "[entrypoint] Starting script-engine-backend..."
echo "[entrypoint] APP_ENV=${APP_ENV:-development}"

if [ "${APP_ENV}" = "production" ]; then
    echo "[entrypoint] Running database migrations..."
    cd /app && python -c "from database import init_db; import asyncio; asyncio.run(init_db())" || echo "[entrypoint] DB migration skipped (will retry on health check)"
fi

exec "$@"
