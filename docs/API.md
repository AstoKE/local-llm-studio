# API

Backend: `http://127.0.0.1:8000`; browser uses same-origin `/api` through Next.js. Interactive schemas: backend `/docs`.

| Method | Path | Behavior |
|---|---|---|
| GET | /api/health | Database connectivity and current phase |
| GET | /api/dashboard | Provider status/models/loaded, real system metrics, recent persisted records and active jobs |
| GET | /api/models | Installed metadata; 503 when unavailable |
| GET | /api/models/metadata?model=... | Provider `/show` metadata without invented fields |
| POST | /api/models/{pull,delete,load,unload} | Administrator-only operation; pull streams NDJSON |
| GET/POST | /api/conversations | Search by `q`, or create with title/model/configuration |
| GET/PUT/DELETE | /api/conversations/{id} | Detail with messages, update, or delete |
| POST | /api/chat | NDJSON inference events; optional conversation_id, edit_message_id or regenerate |
| GET/POST | /api/presets | List/save validated inference configuration |
| DELETE | /api/presets/{id} | Delete preset |
| GET/PUT | /api/model-preferences?model=... | Read/save per-model configuration defaults |
| POST | /api/conversation-snapshots | Explicitly persist a Playground conversation |

Example chat body: `{"model":"<installed-model>","content":"Hello","configuration":{"options":{"temperature":0.5}}}`. Omitting conversation_id makes it transient; stateless callers send bounded `history` entries. Saved chat uses server history. Editing removes the target message and later history before resending. A conversation can have only one active generation.

NDJSON chat events: `{"type":"token","content":"..."}`, `{"type":"done","statistics":{...}}`, or `{"type":"error","detail":"..."}`. Post-header failures appear as error events, not HTTP status changes. An ended stream without `done` is an error. Disconnect closes upstream and saves partial text as interrupted; interrupted/failed assistant output is excluded from future context. Stop closes the client connection; underlying runtime cancellation timing is provider-dependent and needs real verification.

Provider counters/durations are stored unchanged; durations are nanoseconds. `server_ttft_seconds` is an application monotonic-clock measurement from stream start to first content. It is not a provider measurement. GPU memory is MiB, host memory bytes. GPU null and model lists null mean unavailable, distinct from zero or an empty connected list.

All payload schemas forbid unknown fields. Model-operation requests require `Authorization: Bearer <STUDIO_ADMIN_TOKEN>` even from loopback. Set a random secret of at least 32 characters. Browser requests with Origin must match STUDIO_WEB_ORIGIN; cross-site fetches are denied. Unauthenticated chat is intended only for the default localhost deployment. No arbitrary runtime endpoint or shell command is accepted. Do not enable LAN binding yet.

## Phase 3 monitoring

`GET /api/monitoring?minutes=60&model=<optional>&before_id=<optional>` returns:

- `current`: most recent backend host sample; CPU %, memory bytes, GPU list with nullable utilization/% and memory/MiB, source and sampled_at UTC timestamp.
- `system_history`: up to 600 actual observations from the requested range, ordered oldest first. When necessary points are evenly selected, never interpolated or averaged. Host measurements are independent of the model filter.
- `runs`: newest 100 inference attempts, model/source/status, raw `statistics`, and nullable `tokens_per_second`. Pagination uses the last ID as before_id; has_more indicates an older page.
- `models`: retained inference model identifiers (not a runtime catalog).
- `active_jobs`, `stale`, `sampler_error`, configured `interval_seconds` and `retention_hours`.

minutes: 1–10080. before_id: positive integer. Model filter is an exact match. Time range and model filter apply to runs; range applies to host history. HTTP 422 for invalid query bounds. A stale sample (older than three configured intervals) is explicitly flagged. Storage/sampler errors are exposed without returning private configuration.

Raw provider duration fields remain nanoseconds. Output throughput = eval_count / (eval_duration / 1e9), unknown if counters are missing or duration is zero. prompt_eval_cached_count is retained when supplied; prompt evaluation duration is shown as returned rather than inventing a prompt throughput estimate. server_ttft_seconds and server_duration_seconds are application monotonic-clock observations. Failed/interrupted attempts need not have final provider counters and are never counted as successful chart throughput.

`system_samples` and `inference_runs` are added by migration 0002. Sampling persists without any frontend request. Host records expire after the configured retention and are capped at 20,000; inference attempts are capped at 10,000. Performance records deliberately survive conversation deletion and contain no message content or system prompt. No pre-existing message history is backfilled. One backend worker remains required.

## Phase 4 benchmarks and administration

| Method | Path | Behavior |
|---|---|---|
| GET/POST | /api/benchmarks | Paginated summaries (before_id) / start background job, HTTP 202 with id |
| GET | /api/benchmarks/{id} | Saved definition, progress, warm-up/measured results and status |
| POST | /api/benchmarks/{id}/cancel | Cancel active provider stream, retain completed rounds |
| GET | /api/auth/me | Authentication/role/LAN mode flags; no credentials |
| POST | /api/auth/login | Password authentication; HttpOnly session cookie |
| POST | /api/auth/logout | Revoke session and delete cookie |
| GET/PUT | /api/preferences | Read default model/configuration/theme; PUT updates theme only |
| GET/PUT | /api/admin/settings | Administrator-only provider URL and default model/configuration |
| POST | /api/admin/connection-test | Test validated Ollama endpoint without saving |
| GET | /api/admin/health | Database quick_check/revision/counts, runtime/process information |
| POST | /api/admin/maintenance | Administrator-only vacuum or clear_metrics, idle runtime required |

Benchmark body: model, name, prompt, configurations (1–8 named configuration objects), warmups (0–3) and repeats (1–10). Configurations execute in input order; warm-ups precede measured repetitions for each configuration. Only one benchmark is admitted, and admission returns 409 while Chat/Playground/model mutations are active. While benchmarking, new application inference/model mutations return 409. Workloads launched directly through Ollama are outside this admission boundary. Close browser tabs without cancelling to let a benchmark continue. Shutdown cancels the active job; recovery marks orphaned running records interrupted.

Each result retains unchanged provider token/duration counters and application-clock first-token/elapsed timings. RAM peak is sampled whole-host memory (250ms), not model allocation; GPU peaks use only background observations timestamped during the run and may be unavailable for short runs. Warm-ups and failed results are excluded from UI comparison means. Definitions/test prompts and results persist in records(kind=benchmark). No generated response text is saved by the benchmark service. Measured attempts also appear in inference monitoring with source=benchmark; warm-ups do not.

LAN mode protects all backend routes except login/me and requires secure cookies over the configured HTTPS origin. Admin endpoints/model mutations also accept the existing Bearer token. Sessions are stored as digests, expire, revoke on logout and invalidate on password-hash rotation. No password hash or API token is returned by settings endpoints. Provider URLs containing credentials/query/fragment are rejected. Preferences use server-side allowlists. The original localhost and Phase 1–3 security descriptions are superseded by docs/LAN_ACCESS.md for optional LAN deployment.

## Phase 5 request and disconnect guards

Health reports phase 5 (application version 0.5.0); schema remains 0002. Unconfigured Host names return HTTP 400 at both frontend proxy and backend. Browser mutation Origin still separately enforces scheme/port. Requests exceeding STUDIO_MAX_REQUEST_BYTES (default 2 MiB, configurable 64 KiB–16 MiB) return HTTP 413 before JSON parsing, including chunked bodies. Unsupported/invalid parameters remain HTTP 422. No CORS wildcard is introduced.

Chat/download resource admission is released even when the client disconnects before response headers or stream iteration starts. If generation never started, there is no invented completion/performance record; an already saved user message can still be retried/regenerated. API responses remain no-store. New verification and deployment tools are documented in TESTING.md and DEPLOYMENT.md.
