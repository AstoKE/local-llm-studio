# Local LLM Studio

Linux-first local inference workspace: Next.js App Router, TypeScript, Tailwind, Radix/shadcn-style primitives, Recharts, FastAPI, SQLAlchemy, Alembic and SQLite. No cloud service is required.

Phase 2 implements streaming Ollama chat, saved conversations, model management and inference configuration. Hardware inference and production-browser acceptance still require local verification; see [testing](docs/TESTING.md).

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

## Phase 2 usage

- **Chat:** select an installed model, configure inference, send a message. Conversations and settings persist locally. Search, rename, delete, copy, edit/resend, regenerate and stop are available. Editing removes later messages.
- **Playground:** inference without conversation persistence; explicitly save the session to continue later in Chat.
- **Models:** filter installed models, inspect metadata, download by exact identifier, load/unload or delete. Ollama exposes no searchable remote catalog endpoint; browse its library to discover identifiers.
- **Configuration:** bounded sampler options, system prompt, stop sequences, keep-alive, saved presets and model-specific defaults. Unsupported frequency/presence penalties and GPU layer controls are visibly excluded and rejected by the API.

For model operations, generate a secret with `.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))'`, put it in `.env` as `STUDIO_ADMIN_TOKEN`, restart the backend and enter it in Models. The UI keeps it in page memory only. No secret is embedded in frontend assets. Keep both servers on localhost; LAN authentication remains Phase 4 work.

If opening the frontend with a hostname other than `127.0.0.1`, set `STUDIO_WEB_ORIGIN` to its exact origin and restart FastAPI. It defaults to `http://127.0.0.1:3000` for cross-origin request protection.

See [Linux setup](docs/SETUP_LINUX.md), [architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [feature status](docs/FEATURES.md), and [verification](docs/TESTING.md).
