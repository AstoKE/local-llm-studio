# Linux setup

Install Python with venv support, Node.js 20.9+ and npm using your distribution's package manager or official installers. Follow the root README to install application dependencies. Always run backend commands from the repository root so `.env` and relative SQLite paths resolve consistently.

## Ollama

Install from https://ollama.com/download/linux after reviewing the installer. Run `ollama serve` in a terminal, or start its system service if installed. Confirm with `curl http://127.0.0.1:11434/api/version`. Select a model from https://ollama.com/library, then run `ollama pull <model:tag>`. List installed models with `ollama list`. Keep Ollama listening only on loopback.

Ollama is optional for viewing the interface: a stopped service produces an offline banner, and CPU/RAM telemetry still works. No model is automatically downloaded or loaded.

## Local deployment

Run migrations with `mkdir -p data && .venv/bin/alembic upgrade head`, then `./scripts/backend.sh`. For a production frontend, run `npm run build` and `npm start` in `apps/web`. Use a service manager to supervise each process, with the repository as backend WorkingDirectory. Optional Docker Compose packaging is deferred.

## LAN access

LAN mode is deliberately not enabled in Phase 1. Do not change the Next.js binding to `0.0.0.0`: its API proxy would bypass the preliminary backend remote-IP check. Phase 4 must supply authenticated proxy/session setup, TLS and administrator authorization before remote device access is supported. Never forward ports to the internet or expose Ollama. Until then, use a trusted SSH tunnel to the localhost frontend if remote access is necessary.

## Troubleshooting

- Offline Ollama: check its service and the server-side `STUDIO_OLLAMA_URL`; restart FastAPI after changes.
- Database missing: run migrations from repository root; ensure `data/` is writable.
- Backend unavailable: start FastAPI on port 8000; inspect its terminal log.
- GPU unavailable: check vendor drivers. CPU/RAM remain usable. AMD/Intel telemetry is currently unavailable rather than guessed; future adapters may expose it.
- Install fails with DNS/network errors: dependencies require network for initial download. Runtime can work offline after dependencies and models exist.
- Memory errors during future inference: choose smaller or more quantized models and reduce context; this application does not yet launch inference.
