# Testing and verification

The current acceptance record is [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Automated fixtures do not verify real inference, GPU acceleration, TLS or production browser behavior.

## Available automated checks

From repository root, after dependency installation:

```bash
./scripts/verify.sh
```

The runner executes 34 backend tests, migration preservation/ORM drift/integrity checks, 13 frontend helper tests, TypeScript, shell syntax and production build. It does not suppress failures. --skip-build is available for constrained development only and prints an explicit skip; it is not release acceptance.

Individual commands:

```bash
.venv/bin/python -m unittest discover -s backend/tests -v
.venv/bin/python scripts/check_migrations.py
npm test --prefix apps/web
npm run typecheck --prefix apps/web
npm run build --prefix apps/web
```

Backend tests use temporary SQLite and deterministic httpx providers, never the user's database or an automatic model download. I/O dispatch is executed inline by a test wrapper because this sandbox can stall thread-to-event-loop wakeups/shutdown; real background runtime integration still needs host checks. The migration script separately tests upgrade/downgrade with existing chat data, ORM agreement and SQLite integrity.

Coverage includes saved/transient chat, edits/regeneration, presets/defaults, failed/interrupted/early-disconnected streams, admission release, benchmark sequencing/warm-up exclusion/cancellation/recovery, metrics retention/downsampling, GPU fallback parsing, administrator session expiry/revocation/credential rotation, login limits, Origin/Host checks and bounded declared/chunked requests. Frontend tests cover UTF-8/NDJSON framing/errors, selection despite failed/delayed preferences, GPU identity/null values, benchmark comparison exclusion/means and host/LAN-mode parsing.

## Browser fixture suite

Five scenarios run on Chromium desktop and mobile configurations: Chat/Playground four-model selection despite preference failure, fixed-height chat with internal scroll/right sidebar, explicit Playground saving, and missing GPU/empty monitoring states. Runtime page errors and React hydration/hook console errors fail tests. All /api routes are browser fixtures; no user conversations, runtime models or database are touched. This verifies UI behavior only, not actual streaming timings or the Next.js-to-backend security boundary.

The browser runner is isolated under tests/browser so production dependency locks are unchanged:

```bash
npm install --prefix tests/browser
npm run install-browser --prefix tests/browser
npm run build --prefix apps/web
npm test --prefix tests/browser
```

It starts an isolated production frontend on localhost:3005, without reusing a running server. Port 3005 must be free. A successful production build is required before starting it. Reports/traces/screenshots are gitignored. The optional Playwright package could not be installed from the agent's offline cache, so these tests were syntax-parsed but **not executed**. After installing on the host, review/commit its generated package-lock.json to capture the resolved test dependencies.

## Real HTTP/inference smoke

Start normal backend/frontend and Ollama, then:

```bash
.venv/bin/python scripts/smoke.py
.venv/bin/python scripts/smoke.py --inference --benchmark --model '<installed-model-id>'
```

The default is read-only health/frontend/provider discovery. Explicit inference tests a real transient chat and saves only its monitoring metadata. Explicit benchmark runs one short repetition and saves its definition/results. Select a real installed model; no model name is hardcoded and no download/deletion/unload is performed. Generated content and secrets are not printed. In LAN mode set STUDIO_SMOKE_ADMIN_TOKEN through environment and use HTTPS URLs; --ca-file accepts a trusted local CA. Certificate checking is never disabled. On interrupted benchmark smoke, cancellation is attempted.

The agent's smoke attempt failed with a socket permission error; prior curl attempts could not reach localhost backend/Ollama. This does not mean the user's services are stopped. Previously supplied real chat screenshots are user-provided evidence, not a new phase-5 inference test.

## Host/manual acceptance

1. Restart backend/frontend, confirm health phase 5 and schema 0002. Existing chats should remain intact. Try all seven routes and browser console on narrow/desktop viewports.
2. Verify Chat streams incrementally, stop releases runtime, edit truncates history, regenerate replaces the response and reload restores messages/settings. Repeat in Playground and confirm persistence only when explicitly saved.
3. Confirm model discovery/download/load/unload/deletion using a model you intend to modify. Missing/wrong credentials must block mutations; missing provider fields must stay unknown.
4. Compare monitoring with host tools. Close browser and confirm sampling continues, then restart and confirm history remains. Inspect actual provider token/duration values and application TTFT labeling. GPU sysfs/device memory is not model allocation.
5. Run a two-configuration benchmark with one warm-up and two measured repetitions: six executions total, four measured. Check contention rejection, cancellation, failure/restart recovery and means excluding warm-ups. Avoid external Ollama workloads.
6. Verify Settings/defaults/theme, authorized idle maintenance and preserved chats/benchmark results. Exercise session expiry, password rotation and logout.
7. Complete production, container/user-service and second-device TLS checks in DEPLOYMENT.md/LAN_ACCESS.md. Obtain a current dependency advisory scan on a network-capable host; an offline audit zero is not a security certification.

Actual driver availability, background executor behavior, production proxy, Caddy trust and container/service runtime remain distinct acceptance items. See SECURITY.md for scope and limitations.

## Native LAN deployment generation

Six additional tests verify private-IP/unprivileged-port validation, localhost service routing, captured Node PATH, preservation of existing .env secrets/database settings, staging without host changes, dependency failure before mutation, private file modes and symlink/control-character rejection. No test installs services or changes the OS trust store. The user later reported that host verification, real-model flows and manual browser use passed. Native service activation and actual second-PC HTTPS testing remain pending; see LAN_QUICKSTART.md.
