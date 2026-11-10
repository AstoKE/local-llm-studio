# Local LLM Studio

Linux-first local inference workspace: Next.js App Router, TypeScript, Tailwind, Radix/shadcn-style primitives, Recharts, FastAPI, SQLAlchemy, Alembic and SQLite. No cloud service is required.

Local streaming chat, model management, persistent monitoring, sequential benchmarking and administrator settings are implemented. Phase 5 adds security regressions, verification tooling and deployment examples; production acceptance still has host-only checks outstanding. Hardware inference and production-browser acceptance still require local verification; see [testing](docs/TESTING.md).

## Start

Requires Python 3.11+ and Node 20.9+ (Node 24 recommended for frontend tests).

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock.txt
cp .env.example .env
cd apps/web
npm ci
cd ../..
./scripts/backend.sh
# In another terminal:
./scripts/web.sh
```

Open http://127.0.0.1:3000. Backend listens on 127.0.0.1:8000; startup applies migrations. Start Ollama separately with `ollama serve`. Choose an exact model identifier from https://ollama.com/library appropriate for your memory.

## Chat and model usage

- **Chat:** select an installed model, configure inference, send a message. Conversations and settings persist locally. Search, rename, delete, copy, edit/resend, regenerate and stop are available. Editing removes later messages.
- **Playground:** inference without conversation persistence; explicitly save the session to continue later in Chat.
- **Models:** filter installed models, inspect metadata, download by exact identifier, load/unload or delete. Ollama exposes no searchable remote catalog endpoint; browse its library to discover identifiers.
- **Configuration:** bounded sampler options, system prompt, stop sequences, keep-alive, saved presets and model-specific defaults. Unsupported frequency/presence penalties and GPU layer controls are visibly excluded and rejected by the API.

For model operations, generate a secret with `.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'`, put it in `.env` as `STUDIO_ADMIN_TOKEN`, restart the backend and enter it in Models. The UI keeps it in page memory only. No secret is embedded in frontend assets. Keep both servers on localhost; use the documented HTTPS gateway for optional authenticated LAN access.

If opening the frontend with a hostname other than `127.0.0.1`, set `STUDIO_WEB_ORIGIN` to its exact origin and restart FastAPI. It defaults to `http://127.0.0.1:3000` for cross-origin request protection.

See [Linux setup](docs/SETUP_LINUX.md), [architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [feature status](docs/FEATURES.md), and [verification](docs/TESTING.md).

## Phase 3 monitoring

Restart the backend with `./scripts/backend.sh` to apply migration **0002**, then refresh the frontend. Existing conversations are preserved. Monitoring shows host CPU/RAM, GPU utilization and device memory where drivers expose them, provider token counters and timing breakdowns, server-clock first-token latency, model filtering and paginated generation history.

The backend samples even when the browser is closed. Defaults: five-second sampling delay, 24-hour host history (at most 20,000 samples) and at most 10,000 inference records. Change STUDIO_METRICS_INTERVAL_SECONDS or STUDIO_METRICS_RETENTION_HOURS in .env if needed. Playground performance metadata is recorded; its prompts and responses are not stored in monitoring history. Existing older messages are not backfilled with invented metrics.

Provider-derived tokens/second uses eval_count / eval_duration; first-token and server duration are separate application-clock observations. A missing measurement remains unknown. AMD sysfs support is best effort; Intel devices without exposed counters show unavailable fields. See docs/TESTING.md for verification limits and local acceptance steps.

## Phase 4 benchmarks and administration

**Benchmarks** runs up to eight inference configurations sequentially with optional warm-ups and repeated measurements. Results persist with the prompt/configuration, progress, token rates, timings and sampled whole-host memory peaks. Select saved benchmarks to compare models/configurations; external workloads and different prompts/hardware can affect comparisons. A running benchmark reserves application inference/model operations. It continues if the browser closes and can be cancelled in the UI.

**Settings** supports Ollama endpoint/connection tests, default model and inference settings, dark/light/system appearance, health information, SQLite compaction and monitoring-history cleanup. Administrator actions require either a signed-in administrator session or your existing API token. Settings preserves provider changes across restarts; saved endpoint settings take precedence over STUDIO_OLLAMA_URL.

For password login, run `.venv/bin/python scripts/password_hash.py`, paste the generated hash into .env and restart the backend. Local chat remains usable without login; model operations/administration remain protected. No new dependencies or database migration beyond 0002 are needed for Phase 4.

Optional HTTPS LAN mode is documented in [LAN_ACCESS.md](docs/LAN_ACCESS.md), with an example Caddy configuration. Both application processes and Ollama remain localhost-only. LAN mode is not enabled automatically; actual second-device/TLS/production-browser verification is still required.

## Phase 5 verification and deployment

Run `./scripts/verify.sh` for automated checks and production build. For real services use `.venv/bin/python scripts/smoke.py`; add `--inference --benchmark --model '<installed-model-id>'` to explicitly exercise a real model. Fixture tests never count as real inference verification.

[TESTING.md](docs/TESTING.md) documents the optional desktop/mobile browser suite. [DEPLOYMENT.md](docs/DEPLOYMENT.md) covers native production, user systemd examples and optional Linux Docker Compose. [SECURITY.md](docs/SECURITY.md) records the security boundary. The exact passed/blocked/prepared status is in [RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md); a successful production build, browser/LAN and deployment runtime verification are still required on the host.

## Native HTTPS installation

For the existing workstation database, [LAN_QUICKSTART.md](docs/LAN_QUICKSTART.md) provides a native production installer: `.venv/bin/python scripts/deploy_lan.py --address <workstation-LAN-IP> --apply`. It requires Caddy and an accessible user systemd session, builds the frontend, backs up configuration/database, prompts for an administrator password if needed and enables backend/web/private HTTPS services. It does not modify firewalls, client trust stores or public routing. Installation and a second-device test must be completed on the actual host.
