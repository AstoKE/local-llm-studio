# Phase 1 API

Backend: `http://127.0.0.1:8000`; browser uses same-origin `/api` through Next.js. Interactive schema at `/docs` on backend. No mutation endpoints exist yet.

| Method | Path | Response |
|---|---|---|
| GET | /api/health | Application status, database connectivity, phase |
| GET | /api/models | Raw installed model metadata under `models`; 503 if provider unavailable |
| GET | /api/dashboard | Ollama status/models/loaded, host metrics, persisted recent conversations/benchmarks, active jobs |

Dashboard returns HTTP 200 on Ollama failure with `ollama.connected=false`, explanatory error and null model lists. Null lists mean unknown, unlike empty lists meaning connected with no models. Host bytes use bytes; GPU memory uses MiB. GPU null means unavailable, not zero utilization. CPU percentage is psutil's host sample, not an inference measurement. History is browser-session only. Active jobs is zero because Phase 1 provides no inference jobs.

Provider HTTP, connection and invalid JSON failures map to sanitized 503 messages. Health requires a migrated, writable database. Unexpected database errors remain HTTP 500 and should be investigated in server logs.

Direct non-loopback backend traffic requires `Authorization: Bearer <STUDIO_ADMIN_TOKEN>` with a secret at least 32 characters long. This alone does not implement LAN frontend authentication. Keep default loopback binding.
