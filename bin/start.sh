#!/usr/bin/env bash
set -euo pipefail

echo "[start] PORT=${PORT:-<not-set>} WEB_CONCURRENCY=${WEB_CONCURRENCY:-1}"

# Ejecuta gunicorn ASGI con uvicorn worker, escuchando SIEMPRE en 0.0.0.0:${PORT}
exec python -m gunicorn invpanel.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT} \
  --workers ${WEB_CONCURRENCY:-1} \
  --access-logfile - \
  --error-logfile -
