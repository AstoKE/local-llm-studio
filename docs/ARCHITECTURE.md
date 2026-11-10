# Architecture

## Request and runtime boundaries

Local browser → Next.js same-origin API rewrite → loopback FastAPI → provider adapter → loopback Ollama → host hardware.

Optional LAN browser → HTTPS gateway bound to a private IP → loopback Next.js → loopback FastAPI. Both application processes and Ollama retain loopback listeners. No cloud component is required; the LAN gateway can issue certificates through its local CA.

Next.js owns presentation, navigation, Markdown rendering, NDJSON decoding and charts. FastAPI owns validation, authorization, persistence, runtime admission, benchmark orchestration and host telemetry. The browser never selects an arbitrary proxy path or receives server environment secrets. Initial support is Ollama; the provider contract separates status/model operations and asynchronous chat/download streams from application workflows. Future llama.cpp/vLLM/OpenAI-compatible adapters should implement capabilities and explicit option validation before enabling settings in the UI. Administration currently identifies its endpoint as Ollama-specific.

## Persistence

SQLAlchemy/SQLite is managed by explicit Alembic revisions applied by scripts/backend.sh:

- 0001: conversations, messages and structured records.
- 0002: indexed system_samples and inference_runs.

Conversations persist selected model/configuration. Editing a user message truncates later messages; regenerate replaces the last assistant response. Failed/interrupted assistant output is retained with a status but excluded from subsequent model context. Playground does not persist message content unless explicitly saved as a conversation.

Structured records hold presets, per-model preferences, application defaults, benchmark definitions/results and hashed session records. Saved provider settings take precedence over the environment fallback at restart. Theme/default inference preferences are separately exposed from administrator settings; secrets and password hashes are never returned. Monitoring rows deliberately contain no prompts/system prompts/output text. Benchmark definitions intentionally retain the user-supplied test prompt and configuration, without generated response text.

## Streaming and admission

Provider streams map to token/done/error NDJSON events. After headers have been sent, failures are explicit stream events. A stream ending without completion is an error. Closing the client connection closes the upstream iterator, preserves partial saved-chat output and releases active-job state; the runtime controls actual cancellation latency.

Process-local admission permits concurrent unrelated chats but serializes each conversation. Benchmarks require no active application inference/model operations, reserve inference for their lifetime and run configurations/rounds sequentially. Competing benchmark/chat/model operations receive 409. No parallel benchmark mode is exposed. Direct workloads launched outside this application cannot be controlled. Use **one backend worker**.

Benchmark tasks survive browser disconnection. Optional warm-ups precede each configuration's measured repetitions; only successful measured results contribute to comparison means. Cancellation closes the provider iterator, retains completed rounds and releases admission. Shutdown cancels a job; startup marks orphaned running records interrupted. Provider failures preserve a failed result rather than producing a success measurement.

## Performance and hardware

The lifespan-managed sampler runs independently of frontend requests. Blocking host/SQLite sampling work uses asyncio's executor. The last sample is cached for dashboard reads; the Monitoring API flags stale observations and sampler/storage failures. A storage lock coordinates recording with database maintenance. Host history expires after the configured duration and is additionally capped at 20,000 observations; inference history is capped at 10,000 attempts. Charts select at most 600 actual points and never invent missing values.

NVIDIA uses fixed-argument nvidia-smi subprocesses with timeout/cancellation cleanup, never a shell. Read-only DRM/sysfs adds available AMD measurements and partial device enumeration for Intel/other systems. Missing utilization/VRAM fields remain null. Stable device IDs distinguish GPU series. CPU/RAM and GPU readings are whole-host/device measurements, not model allocations.

Ollama token counters and nanosecond durations are preserved. Output throughput derives from eval_count / eval_duration; TTFT and stream lifetime are labeled application monotonic-clock observations. Benchmark RAM peaks are sampled every 250ms plus endpoints. GPU peaks use only background observations timestamped during the run, so short runs can have no GPU observation. Warm-up attempts do not enter inference monitoring history.

## Authentication and security

Localhost chat remains usable without login. Administrator actions (model mutation and administration) always require either a valid browser session or a configured bearer token. LAN mode additionally protects all backend routes except login/session-status. Backend authorization is authoritative; Next.js proxy provides page-level login redirection and fails closed when session validation is unavailable.

Passwords are configured as scrypt hashes in environment variables. Login checks constant-time digest comparison, rate limits failed attempts, rotates sessions and returns HttpOnly/SameSite=Strict cookies (Secure in LAN mode). SQLite stores only a SHA-256 digest of the random session token, expiry, role and credential version. Logout revokes it; expiry or password-hash rotation invalidates it. Secrets never enter localStorage; theme preference may. The current identity model is a single administrator and a local-mode principal, not a multi-user ownership/RBAC system.

Mutation requests reject unexpected Origin/cross-site headers. Loopback hostname aliases are allowed only on the configured origin's scheme/port. All API responses use no-store. Inputs use bounded Pydantic schemas that reject unknown settings. Provider URLs reject embedded credentials, fragments and queries. No arbitrary shell execution or SQL endpoint exists; maintenance allows only idle SQLite vacuum/monitoring cleanup. LAN startup requires an HTTPS origin and valid password hash. Never expose Ollama publicly. See LAN_ACCESS.md for deployment and remaining verification.

## Verification and remaining work

Phase 4 implements benchmarking and initial administration/LAN security. Test results and limitations are recorded in TESTING.md; fixtures are not real inference, TLS, proxy or browser verification. Production build and hardware/second-device acceptance remain required. Phase 5 provides broader security/transport regressions, a prepared browser fixture suite, disposable migration verification, real-service smoke tooling, native user-service examples and optional Linux Compose/standalone packaging. Production/runtime acceptance remains in RELEASE_CHECKLIST.md; full multi-user/RBAC is not implemented.

References: [Next.js Proxy](https://nextjs.org/docs/app/api-reference/file-conventions/proxy), [Ollama native API](https://github.com/ollama/ollama/blob/main/docs/api.md), [AMDGPU sysfs](https://docs.kernel.org/gpu/amdgpu/driver-misc.html), [Caddy local TLS](https://caddyserver.com/docs/caddyfile/directives/tls).

## Phase 5 hardening

FastAPI and Next.js validate actual Host names against loopback/configured origins before trusted API proxying. A body-limiting ASGI middleware bounds JSON buffering (2 MiB by default), including chunked requests, without buffering response streams. ManagedStreamingResponse closes iterators and releases resource admission even if response headers cannot be sent. These cases have explicit regression tests.

Deployment keeps existing API URLs with Next.js standalone output and loopback Linux host-network Compose services. Backend data is a separate named volume; secrets/data/tests are excluded from image context and containers use non-root/read-only defaults. Native production scripts and user-service examples preserve local binding. No infrastructure was published or enabled automatically. See DEPLOYMENT.md for operator setup and verification limits.
