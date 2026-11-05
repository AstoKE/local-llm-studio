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

## Phase 2 verification update (2026-11-05)

Dependencies were subsequently installed by the user. Current results supersede initial dependency-blocked results above:

- PASS: `.venv/bin/alembic upgrade head` and `.venv/bin/alembic current` — revision 0001.
- PASS: `npm run typecheck` in apps/web.
- PASS: nine backend tests via `.venv/bin/python -m unittest discover -s backend/tests -v`. Isolated temporary SQLite with ASGITransport; deterministic httpx fixtures, not actual inference. Covers conversation CRUD/history, edit/regenerate, presets, model defaults, explicit snapshots, Playground isolation, partial/disconnected and incomplete streams, job cleanup, administrator authorization, cross-origin rejection and unsupported parameter rejection.
- PASS: three frontend transport tests via `npm test` in apps/web (Node 24). Run without test-process isolation because sandbox child-process behavior can otherwise report only the wrapper file. Covers split UTF-8/NDJSON, authorization/error handling and reader cancellation.
- PASS: Python source compilation.
- BLOCKED: production build fails at child-process invocation of `tsc --showConfig`. A direct Node spawnSync reproduction returns EPERM; directly running TypeScript works. No successful production build is claimed. Run `npm run build` on the host.
- UNAVAILABLE from this sandbox: localhost backend and Ollama HTTP services. User reports backend/frontend startup works on host. No real model, GPU or browser end-to-end verification is claimed.

### Required host acceptance for Phase 2

1. Start Ollama, backend and frontend. Check health and model listing; run `npm run typecheck`, `npm test` and `npm run build`.
2. Configure STUDIO_ADMIN_TOKEN, restart backend. Confirm missing/wrong token blocks mutations. Download a chosen model and inspect progress, metadata and loaded state. Test load/unload/delete only with a model you intend to modify.
3. Chat: verify incremental text, stop while generating, reload saved conversation, rename/search/delete, edit an earlier prompt, regenerate. Confirm the model receives the intended history.
4. Save/load a preset and per-model defaults. Ensure invalid/unsupported options return 422. Observe actual model memory limits for context size.
5. Playground: generate without a saved conversation; explicitly save it and open it in Chat. Inspect code rendering, narrow viewport and console errors.
6. Stop Ollama during a response; verify error state, retained partial text and released active-job count. Confirm future history excludes failed assistant output.
7. Keep localhost binding. LAN/RBAC acceptance remains a later phase.

No real model downloads, deletions or loads were performed automatically in this environment. The developer did not create the Phase 1 commit because .git is read-only to the agent; commit 0cfe0fe (Phase 1) became visible during work.

### Chat hot-reload and send fixes

Frontend hot updates now remount ChatWorkspace (`@refresh reset`) when its hook structure changes. Sending errors survive the subsequent conversation reload; missing-model state has a retry action, waiting responses have a status, Enter submits and Shift+Enter inserts a newline. Browser acceptance still needs a host check.

Origin checks accept localhost/127.0.0.1/IPv6 loopback aliases only on the configured scheme and port; other hosts/ports and cross-site requests stay denied. Eleven backend tests pass, including a browser-origin conversation-create/chat flow with localhost and propagation of an actual provider error fixture. TypeScript and three frontend transport tests pass. These remain fixture-based tests, not live Ollama/browser verification. Restart FastAPI after this update and fully reload the frontend to clear stale development hook state.
