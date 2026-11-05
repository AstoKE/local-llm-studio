# Verification

## Results in development environment (2026-11-05)

- PASS: `python3 -m unittest discover -s backend/tests -p test_provider.py -v` — 3 tests, protocol paths/metadata preservation, HTTP failures, invalid JSON and connection failures, using httpx MockTransport. These are unit tests, not real inference verification.
- PASS: `python3 -m compileall -q backend`.
- PASS: live `system_snapshot()` check — nonzero RAM total and CPU percentage in range; returned 16 logical CPUs, 15,961,358,336 bytes total RAM and GPU null.
- OBSERVED: AMD Ryzen 7 7735HS with Radeon Graphics; Python 3.13.11, Node 24.22.1, npm 11.19.1.
- OBSERVED: Ollama executable reports client 0.40.3, service not running. HTTP connection to localhost:11434 refused.
- OBSERVED: nvidia-smi exists but cannot communicate with NVIDIA driver. Actual GPU utilization/VRAM have not been verified. DRM device nodes alone do not prove working inference acceleration.
- BLOCKED: Python dependencies failed DNS resolution. Cached dependencies insufficient (SQLAlchemy/Alembic absent). Migration and backend API integration remain unverified.
- BLOCKED: npm dependency installation cannot reach registry; offline install lacks Radix cache. Frontend typecheck reports `tsc: not found`; build reports `next: not found`. No frontend build or browser verification claimed. No dependency lockfiles generated.
- NOT VERIFIED: real model inference, model loading, downloads, token statistics, benchmark measurements, GPU acceleration and remote-device authentication. Most are later-phase features.

## Repeatable checks after dependency installation

From repository root:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/python -m compileall -q backend
mkdir -p data
.venv/bin/alembic upgrade head
.venv/bin/alembic current
./scripts/backend.sh
```

In another terminal:

```bash
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/dashboard
cd apps/web
npm run typecheck
npm run build
npm start
```

API integration test uses an isolated temporary database, actual Alembic migration and an intentionally unreachable provider. Verify connected-provider paths separately with a running Ollama service and compare `/api/models` against `ollama list` and loaded models against `ollama ps`.

Browser acceptance: all seven routes, narrow viewport navigation, refresh, offline banner, backend failure state, no-model empty state, real model metadata and session chart accumulation. Inspect browser console and ensure no external requests or exposed secrets. This manual frontend check has not yet run. Automated frontend tests are still required in Phase 5.

Do not progress beyond Phase 1 acceptance until its blocked checks pass. Freeze resolved dependencies, review security advisories and commit lockfiles before production deployment.
