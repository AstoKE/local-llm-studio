# Milestones

| Phase | Implementation | Verification / remaining work |
|---|---|---|
| 1 Foundation | Layout, navigation, SQLite/Alembic, provider adapter, runtime status, CPU/RAM and optional NVIDIA telemetry | Migration and TypeScript pass; production build blocked by sandbox child-process EPERM; browser check remains local |
| 2 Core | Streaming chat; conversation CRUD/search; edit/resend/regenerate/stop; Playground and explicit snapshot save; installed-model filtering, metadata, pull progress, delete/load/unload; inference options, system prompt, presets and model defaults | Nine backend tests and three frontend stream tests pass; real Ollama inference, downloads, browser interactions and GPU behavior remain unverified |
| 3 Monitoring | Host sampling/session chart and provider statistics on messages already available | Persistent performance history and expanded timing charts pending |
| 4 Benchmark/admin | Model-operation bearer authorization is present | Sequential benchmarks, warm-up/repeats, settings administration, authenticated LAN sessions pending |
| 5 Deployment | Documentation, lockfiles and initial tests provided | Browser automation, deployment packaging and full security/real-hardware acceptance pending |

Markdown currently supports safe plain text, paragraphs, headings, bold, inline code and fenced blocks with basic syntax coloring. Full CommonMark tables/links/lists and language-specific highlighting remain a UI improvement. The runtime does not expose a remote catalog search API, so discovery links to the official library and downloads require exact identifiers. Unsupported settings are rejected rather than ignored.

The application is not declared production-ready. Do not progress to Phase 3 until the Phase 2 local acceptance checks in TESTING.md pass.
