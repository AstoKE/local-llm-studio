#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export NEXT_TELEMETRY_DISABLED=1
studio_production=false
if [[ "${1:-}" == '--lan' ]]; then
  export STUDIO_LAN_MODE=true
  studio_production=true
elif [[ "${1:-}" == '--production' ]]; then
  studio_production=true
elif [[ $# -gt 0 ]]; then
  echo 'Usage: scripts/web.sh [--lan|--production]' >&2
  exit 1
fi
export STUDIO_LAN_MODE="$(.venv/bin/python -c 'from backend.core.config import settings; print(str(settings().lan_mode).lower())')"
if [[ "$STUDIO_LAN_MODE" == 'true' ]]; then
  .venv/bin/python -c 'from backend.core.config import settings; assert settings().web_origin.scheme == "https" and settings().admin_password_hash, "LAN mode requires HTTPS STUDIO_WEB_ORIGIN and STUDIO_ADMIN_PASSWORD_HASH"'
fi
export STUDIO_WEB_ORIGIN="$(.venv/bin/python -c 'from backend.core.config import settings; print(settings().web_origin)')"
cd apps/web
if [[ "${STUDIO_LAN_MODE:-false}" == 'true' || "$studio_production" == 'true' ]]; then
  exec npm run start
fi
exec npm run dev
