#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
.venv/bin/alembic upgrade head
exec .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
