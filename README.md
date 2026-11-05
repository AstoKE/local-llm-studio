# Local LLM Studio

A Linux-first local inference workspace built with Next.js App Router, TypeScript, Tailwind, shadcn-style Radix UI primitives, Recharts, FastAPI, SQLAlchemy, Alembic and SQLite. No cloud services or hosted assets are required at runtime.

**Current milestone: Phase 1 implementation. Full application and production readiness are not complete.** The dashboard reads host CPU/RAM and Ollama status, installed models and loaded models. Seven navigation routes provide a shared dark interface; later-phase sections explicitly identify themselves as pending. There is no simulated inference.

## Start

Requires Python 3.11+, Node 20.9+ and npm. From this directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
cd apps/web
npm install
cd ../..
./scripts/backend.sh
# In another terminal:
./scripts/web.sh
```

Open http://127.0.0.1:3000. Backend listens on 127.0.0.1:8000. The backend script runs migrations before starting. Start Ollama separately with `ollama serve`. Model installation is currently via `ollama pull <model:tag>`; choose a model compatible with available memory from the official library.

See [Linux setup](docs/SETUP_LINUX.md), [architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [feature status](docs/FEATURES.md), and [verification](docs/TESTING.md).
