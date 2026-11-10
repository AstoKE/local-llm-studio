# Release acceptance — Local LLM Studio 0.5

Recorded 2026-11-05. **Status: core host checks user-confirmed; persistent services and second-PC HTTPS acceptance remain pending.** A release is not certified by fixture tests alone.

| Check | Result | Evidence / next action |
|---|---|---|
| Backend regressions/security | PASS | 34 tests, including six deployment generation/preflight checks; no live service installation in tests |
| Frontend transport/state helpers | PASS | 13 Node tests |
| Strict frontend typing | PASS | npm run typecheck |
| Migration preservation/schema drift | PASS | Disposable 0001 → 0002 → 0001 → 0002; chats retained, ORM matches, SQLite integrity ok |
| Python/shell syntax | PASS | compileall and bash -n |
| Python dependency consistency | PASS | PYTHONPATH='' .venv/bin/python -m pip check; not a vulnerability audit |
| Compose configuration | PASS | docker compose --env-file /dev/null config --quiet, Compose v5.3.1 |
| Production frontend build | PASS — USER REPORTED | User reports full verification passed on the host; .next/BUILD_ID is present. Agent sandbox build remains blocked. |
| Manual browser use | PASS — USER REPORTED | User manually tested the browser; this is distinct from the automated Playwright suite. |
| Browser fixture suite | PREPARED, NOT RUN | Five cases on desktop/mobile; Playwright package unavailable offline; TS syntax parsed only |
| Real model flows | PASS — USER REPORTED | User reports item 2 checked on the host; agent cannot independently access service sockets. |
| Docker image build/runtime | BLOCKED | Permission denied accessing /var/run/docker.sock |
| User systemd service verification | BLOCKED | systemd-analyze cannot bind/connect its private/system socket in sandbox |
| Current advisory audit | BLOCKED | npm registry audit request fails DNS (EAI_AGAIN); offline audit zero is not evidence of current vulnerability status |
| NVIDIA/GPU acceleration | NOT VERIFIED | Earlier NVIDIA driver communication failed; previous AMD sysfs reads are not proof of inference acceleration |
| HTTPS/second-device LAN access | NOT VERIFIED | Caddy unavailable; certificates/cookies/proxy/browser path require host validation |

The earlier agent-side full scripts/verify.sh run returned **exit 1** due to the production build; it did not mask that failure. --skip-build passes available checks but explicitly does not mean release acceptance.

## Host sign-off

- [x] User reports full verification, including production build, passed on the host.
- [ ] Run the browser suite from TESTING.md; inspect failed traces/screenshots and console errors.
- [x] User reports real-model flows checked on the host; exact scripted smoke output was not supplied.
- [ ] Confirm token counters, timing attribution, cancellation and persistence under real model execution; compare host telemetry with system utilities.
- [ ] Complete an online npm/backend advisory audit and review findings; commit the resolved optional browser-test lockfile after successful installation.
- [ ] If using Docker, build/start images and verify non-root database volume ownership, loopback bindings, health and persistence.
- [ ] If using user services, validate adjusted paths/Node PATH, startup, shutdown and reboot/logout behavior.
- [ ] If enabling LAN, validate the Caddy config, trust its local CA on clients, verify authentication/expiry/logout and actual streaming from a second device.
- [ ] Record OS/runtime/model identifiers and actual test results before describing deployment as production-ready.

## Native LAN setup preparation

The user requested actual HTTPS second-PC testing and persistent production services. scripts/deploy_lan.py and LAN_QUICKSTART.md now prepare native user services, private-IP HTTPS on unprivileged port 8443, .env/SQLite backups, local administrator-password prompting and public-CA export/checks. Six generation/preflight tests pass. The agent cannot discover the workstation LAN IP, access systemd or install Caddy in its sandbox; installation and second-PC acceptance are not marked complete.
