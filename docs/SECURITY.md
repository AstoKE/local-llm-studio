# Security review and deployment boundaries

This is a single-workstation application with one administrator identity. It is not multi-tenant software and has not received an independent penetration test.

## Implemented boundaries

- Native and container app processes bind loopback; LAN mode requires a deliberately configured HTTPS gateway and administrator password hash. Ollama remains private.
- Backend authorization protects all LAN API/data routes except login/status. Model mutation and administrative endpoints always require an authenticated administrator even on localhost. The Next.js proxy also redirects private pages, but backend checks remain authoritative.
- Passwords use salted scrypt; browser session tokens are random, stored only as SHA-256 digests with expiry and credential version. HttpOnly/SameSite=Strict cookies become Secure in LAN mode. Logout/password rotation invalidate sessions. Tokens/password hashes never enter frontend configuration or localStorage.
- Failed login attempts are limited in process memory. All browsers behind the same application proxy share the backend-visible address bucket. Use one worker; multi-process rate limiting/RBAC is not implemented.
- Browser mutations reject cross-site/unexpected origins. Backend and Next.js reject unconfigured Host names, addressing DNS-rebinding access to localhost APIs. Loopback names and the configured web origin hostname are allowed; ports/scheme remain checked by the mutation-origin boundary.
- A configurable 2 MiB request-body limit applies before JSON parsing, including chunked requests. Parameter schemas reject unsupported settings and constrain sizes/ranges. Oversized valid conversation snapshots must be split rather than increasing the bound without considering memory.
- Model output is rendered as React text with a limited Markdown subset; raw HTML is never inserted or executed. External fonts/assets and hosted inference are not required. Next.js telemetry is disabled by the supplied web launcher/container.
- No shell or arbitrary SQL endpoint exists. GPU sampling invokes fixed arguments, read-only kernel files and timeout cleanup. Administrative maintenance is allowlisted and coordinated with recording.
- Streaming admission is released even if the connection fails before headers/iterator startup. Cancellation/benchmark failure cleanup is tested. Upstream runtime cancellation latency still requires live validation.

## Data and operator responsibilities

Conversations and benchmark test prompts are plaintext local data. SQLite is not encrypted. Playground performance records omit message content; explicitly saved Playground sessions and benchmark definitions persist by design. Protect the data directory and backups with workstation permissions and disk encryption if required. Do not commit .env, database files, traces or screenshots containing real user content.

Provider endpoints are administrator-configurable HTTP(S) URLs without embedded credentials/query/fragment. An administrator can intentionally target another endpoint; this is a trusted-operator setting, not a generic public proxy. Avoid untrusted public runtimes. Keep your Linux drivers, Ollama and reverse proxy updated. Other processes sending work directly to Ollama bypass application benchmark contention controls.

The supplied Compose files drop privileges and publish no ports, but Linux host networking intentionally shares the host network namespace to reach loopback Ollama. Review that choice for your threat model; it is not container network isolation. The application does not provision firewall rules, router forwarding, public certificates or cloud resources.

## Verification limits

Automated tests cover authorization, CSRF/origin/Host checks, session expiry/revocation, request size limits, stream cleanup and benchmark admission using fixtures. Dependency consistency is checked separately from vulnerability scanning. Registry/advisory access, a successful production build, real browser/gateway behavior, live models and deployment runtime checks are still required on the host. Passing offline tests does not certify a secure production deployment. See RELEASE_CHECKLIST.md for the exact status.
