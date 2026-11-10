# Local production deployment

Production files are prepared, not yet runtime-certified: see RELEASE_CHECKLIST.md. Always back up data/studio.db with the backend stopped before deployment or migration. Do not overwrite the user's .env.

## Native Linux (recommended)

Install dependencies from backend/requirements.lock.txt and apps/web/package-lock.json as in README. Use Node 24 for the full verification tooling. Run:

```bash
./scripts/verify.sh
./scripts/backend.sh
# Another terminal:
./scripts/web.sh --production
```

verify.sh runs backend tests, disposable migration preservation/ORM drift checks, frontend tests, strict TypeScript, shell checks and a production build. It returns nonzero if a required check fails. --skip-build is only for constrained development environments and explicitly does not satisfy release acceptance. The web script disables Next.js telemetry. Both processes listen on localhost. One backend worker is required.

### User services

Examples are provided under deploy/systemd. Adjust WorkingDirectory and ExecStart if the project is not at ~/code/local-llm-studio. Ensure data/ exists and is writable; build frontend before enabling its service. The backend unit applies migrations automatically and confines writes to data/.

The frontend needs a stable Node/npm PATH. With fnm/nvm, configure an explicit PATH in the web unit using the result of `command -v node`; a systemd user service does not inherit interactive shell initialization. Do not hardcode a Node path copied from another machine. Both scripts read the root .env through Python settings rather than sourcing it as shell code.

After reviewing paths, install the examples into your user systemd configuration and run:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd/local-llm-studio-*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now local-llm-studio-backend local-llm-studio-web
journalctl --user -u local-llm-studio-backend -u local-llm-studio-web -f
```

Service installation/startup is an explicit host action; the agent did not modify user service configuration. User service persistence after logout depends on your system's user-manager/linger policy. LAN deployment adds the authenticated HTTPS gateway described in LAN_ACCESS.md; the application listeners stay local.

## Optional Docker Compose (Linux-only)

Compose 2.30+ is required for raw env_file support; this preserves dollar signs in scrypt hashes. First build needs network access for base images and dependencies. After images/dependencies/models are installed, no cloud service is required. Base images use maintained major-version tags; pin validated image digests in a release environment if byte-for-byte reproducibility is needed.

```bash
cp .env.example .env  # only on a fresh setup; do not overwrite an existing .env
# Configure credentials/endpoints as needed, then:
docker compose --env-file /dev/null config --quiet
docker compose --env-file /dev/null build
docker compose --env-file /dev/null up -d
docker compose --env-file /dev/null logs -f
```

Stop native app processes on ports 3000/8000 before starting Compose. Native Ollama stays on 127.0.0.1:11434. Host networking lets containers reach that loopback endpoint and preserves the same API rewrite URLs. This shares the Linux host network namespace rather than exposing mapped ports; both application commands explicitly bind 127.0.0.1. Do not replace that binding with 0.0.0.0. No privileged mode, Docker socket mount or GPU device passthrough is used. Containers run as non-root with dropped capabilities, read-only root filesystems and /tmp scratch space.

SQLite uses a separate named volume studio-data. It does not automatically import data/studio.db. Never run `docker compose down -v` unless you intend to delete that database. Stop services before exporting/backing up the volume; keep session/database backups private. Inference runs on the host Ollama process, so CUDA is not required inside these images. NVIDIA utilities are not installed in the backend image; sysfs may expose partial GPU telemetry. Verify metric scope/read permissions on your host before interpreting container readings.

For Docker LAN mode set STUDIO_LAN_MODE=true and HTTPS STUDIO_WEB_ORIGIN in .env, generate STUDIO_ADMIN_PASSWORD_HASH and use the host HTTPS gateway from LAN_ACCESS.md. No container port is published publicly. Authentication is enforced in FastAPI independently of the Next.js page redirect.

Compose configuration syntax was validated. Image builds, healthchecks, persistent volume ownership and container runtime behavior remain unverified because the agent cannot access the Docker daemon.

## Verify real services

With app and Ollama running:

```bash
.venv/bin/python scripts/smoke.py
.venv/bin/python scripts/smoke.py --inference --benchmark --model '<installed-model-id>'
```

The first command checks real HTTP health/frontend/provider discovery. The second performs actual stateless inference and one measured benchmark, retaining their performance metadata and the explicitly named benchmark definition. It never downloads, deletes or unloads models. It requires an explicitly selected installed model. No reply text or credentials are printed. In LAN mode supply an administrator token through STUDIO_SMOKE_ADMIN_TOKEN and use HTTPS API/web URLs; a locally trusted CA can be supplied with --ca-file. Verification never disables TLS certificate checks.

A successful HTTP smoke test is not a browser, load or hardware acceleration test. Complete browser and second-device checks in TESTING.md before release.
