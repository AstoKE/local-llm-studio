#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
studio_skip_build=false
if [[ "${1:-}" == '--skip-build' ]]; then
  studio_skip_build=true
elif [[ $# -gt 0 ]]; then
  echo 'Usage: scripts/verify.sh [--skip-build]' >&2
  exit 2
fi
studio_failed=0
run_check() {
  local studio_name="$1"
  shift
  if "$@"; then
    echo "PASS: $studio_name"
  else
    echo "FAIL: $studio_name" >&2
    studio_failed=1
  fi
}
run_check 'Backend tests' .venv/bin/python -m unittest discover -s backend/tests -v
run_check 'Migration preservation / schema drift' .venv/bin/python scripts/check_migrations.py
run_check 'Frontend transport / comparison tests' npm test --prefix apps/web
run_check 'Strict TypeScript' npm run typecheck --prefix apps/web
run_check 'Shell syntax' bash -n scripts/backend.sh scripts/web.sh scripts/verify.sh
if [[ "$studio_skip_build" == 'true' ]]; then
  echo 'SKIP: Production build (explicit --skip-build; this is not release acceptance)'
else
  run_check 'Production build' npm run build --prefix apps/web
fi
exit "$studio_failed"
