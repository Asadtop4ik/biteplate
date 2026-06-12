#!/usr/bin/env sh
set -e
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "Running migrations + seed..."
  alembic upgrade head
  python -m app.infra.seed
fi
exec "$@"
