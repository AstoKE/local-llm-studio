#!/bin/sh
set -eu
alembic upgrade head
exec uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
