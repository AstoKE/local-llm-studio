# Architecture

## Scope and data flow

Browser → Next.js same-origin `/api` rewrite → loopback FastAPI → provider interface → loopback Ollama → host hardware.

Next.js owns presentation and navigation. FastAPI owns validation, authorization, persistence, provider orchestration and host telemetry. The browser never receives provider credentials or selects an arbitrary upstream URL. Endpoint configuration is server-side environment only. HTTP clients disable environment proxy inheritance and have bounded timeouts.

`backend/providers/base.py` defines the initial read-only provider contract; `ollama.py` translates `/api/version`, `/api/tags` and `/api/ps`. Future phases must extend the contract with explicit capabilities, validated inference parameters and cancellable asynchronous event streams before implementing chat or adding llama.cpp/vLLM/OpenAI adapters. Unsupported parameters must be rejected, not discarded.

`backend/services` holds host telemetry; `backend/api` orchestrates responses. SQLAlchemy entities and Alembic revisions live separately. SQLite tables provide conversations, messages and typed structured records for future presets, settings, benchmarks and measurements. The generic records table is a foundation, not implemented feature APIs. Migrations are explicit and run before serving. Future writes need transactions, retention controls and foreign-key enforcement.

## UI

App Router renders a common responsive dark workspace. A small shadcn-style Button uses Radix Slot and class-variance-authority. Lucide supplies icons; Recharts plots only actual session samples. System metrics are polled every five seconds; unavailable GPU values stay unavailable. Models are displayed only from provider responses.

## Security boundary

Default scripts bind both servers to loopback. No CORS wildcard, shell execution API, model mutations or unauthenticated administration endpoints exist. NVIDIA telemetry uses fixed subprocess arguments with a timeout. Remote direct backend requests require a server-configured bearer secret of at least 32 characters. This is a preliminary safeguard, not completed LAN authentication: Next.js rewrites originate on loopback. Do not bind Next.js to a LAN interface until a trusted authenticating reverse proxy and browser session controls exist.

Phase 4 must implement principals, roles, password hashing or external proxy authentication, session expiration, CSRF protection for cookie sessions, rate limiting and administrator checks on downloads/destructive actions. Treat proxy-forwarded identities as untrusted unless the proxy is explicitly trusted. Never expose Ollama publicly.

## Planned execution semantics

Chat: persist input, stream provider events, preserve provider token/duration counters, label application TTFT separately, cancel upstream on disconnect, persist completed/aborted state. Benchmark: one queue, sequential configurations, warm-up excluded from summaries, repeated runs and actual memory samples. Store provider measurements separately from client estimates. None of these workflows is implemented in Phase 1.

## Dependency policy

Version ranges are bounded by major versions. Frontend lockfile and exact Python freeze must be generated after successful dependency resolution. Phase 1 cannot be considered fully verified until migrations, backend API integration tests, frontend type checks, production build and browser checks pass.

References: [Next.js installation](https://nextjs.org/learn/react-foundations/installation), [Ollama API specification](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml).

## Phase 2 implementation update

The provider contract now includes async chat/pull streams and model operations. API workspace routes own conversation CRUD, bounded strict Pydantic options, presets, per-model configuration records and explicit Playground snapshots. `services/chat.py` constructs server history, serializes generation per conversation, persists completed/failed/interrupted responses and releases active-job state. The upstream iterator is explicitly closed. Client disconnects close the stream; actual runtime cancellation behavior must still be tested.

FastAPI and Next.js remain loopback-only. Model operations always require constant-time bearer-token authentication, including requests proxied by Next.js. Browser mutation origin is checked against STUDIO_WEB_ORIGIN; frontend never stores the token in localStorage. This is a single-user local workspace, not completed RBAC or LAN security. Settings and preset data use the existing records table; no new migration is required. Synchronous short SQLite transactions run on the serving process. Use one Uvicorn worker: active conversation locks and job counts are process-local.

Messages hold raw provider statistics and a separate application TTFT measurement. Frontend decodes NDJSON incrementally with UTF-8 support, exposes stop/copy/edit/regenerate and uses safe React text rendering with a limited Markdown subset. No raw HTML from models is executed. Exact dependencies are captured in frontend package-lock.json and backend requirements.lock.txt; successful resolution does not constitute a dependency security audit.

The earlier foundation-only scope paragraphs describe the Phase 1 baseline. Current feature/API status is maintained in FEATURES.md and API.md.

## Phase 3 implementation

`services/monitoring.py` owns a lifespan-managed background sampler. It samples host hardware, caches the last observation for dashboard reads, and writes independent system_samples rows. Blocking CPU/kernel/SQLite sampling work is dispatched to asyncio's thread executor. GPU subprocesses use fixed arguments, bounded timeouts and cancellation cleanup; no shell is invoked. Sampling waits the configured interval after each collection, so actual sample spacing includes collection time and is visible through UTC timestamps. Graceful shutdown cancels the sampler task.

`services/system.py` prefers nvidia-smi measurements and merges additional DRM devices identified through read-only sysfs. AMD gpu_busy_percent/mem_info_vram_* values are read only when exposed. Intel/other unsupported fields remain null. Device IDs allow chart series to distinguish multiple GPUs; source is attached to every device. These whole-host/device readings do not measure the memory attributable to one inference job.

Each inference attempt persists an independent InferenceRun in the stream finalizer, including interrupted/failed attempts and Playground runs. Message content is excluded. Provider token counts/durations retain their original units; calculated throughput is derived from output evaluation, and application TTFT/lifetime are labeled separately. Job locks are released even if message persistence fails. Telemetry persistence failure is logged and does not replace a valid model response.

Migration 0002 introduces the two indexed tables without changing existing chat tables. Bounded retention avoids indefinite growth: system time cutoff plus a 20,000-row cap, inference count cap of 10,000. Monitoring reads are bounded and select up to 600 actual host points; inference pages use stable descending IDs. Recent cache is marked stale rather than presenting old values as live. Browser pause affects polling only. Authentication/LAN and sequential benchmarking remain Phase 4.

References: [Ollama native API](https://github.com/ollama/ollama/blob/main/docs/api.md), [AMDGPU sysfs memory reporting](https://docs.kernel.org/gpu/amdgpu/driver-misc.html), [AMDGPU utilization interfaces](https://kernel.org/doc/html/latest/gpu/amdgpu/thermal.html).
