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
