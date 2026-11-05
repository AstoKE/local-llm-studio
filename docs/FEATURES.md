# Milestones

| Phase | Implemented | Remaining acceptance work |
|---|---|---|
| 1 Foundation | Directory structure, provider abstraction, read-only Ollama adapter, SQLAlchemy schema, Alembic migration, FastAPI routes, navigation, dark design primitives, read-only host/model dashboard | Dependency installation, migration execution, API integration, frontend typecheck/build and browser verification |
| 2 Core | Not started | Streaming chat, persistence APIs, download/search/delete/load/unload, editable inference settings, presets, model overrides |
| 3 Monitoring | Initial CPU/RAM/NVIDIA sampling and session chart provided in foundation | Persistent measurements, real inference statistics, token/timing attribution, additional hardware adapters |
| 4 Benchmark/admin | Not started | Sequential benchmarks, warm-up/repeats, comparison, configuration administration, authenticated LAN mode |
| 5 Verification/deployment | Setup/architecture/API/testing docs and provider unit tests | Full integration/frontend/security tests, real inference, deployment packaging |

Navigation to future sections is intentional and clearly labeled. Settings is informational, with environment-based configuration only. There is no model catalog index, inference engine, account system, benchmark execution, performance fabrication or hidden cloud dependency.
