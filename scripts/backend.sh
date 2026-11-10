#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == '--lan' ]]; then
  export STUDIO_LAN_MODE=true
elif [[ $# -gt 0 ]]; then
  echo 'Usage: scripts/backend.sh [--lan]' >&2
  exit 1
fi
mkdir -p data
.venv/bin/alembic upgrade head
exec .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
