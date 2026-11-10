# Authenticated LAN access

For the existing workstation, use [LAN_QUICKSTART.md](LAN_QUICKSTART.md) and scripts/deploy_lan.py to generate/install native user services with private-IP HTTPS on port 8443. The manual hostname/443 configuration below is an alternative.

Default operation stays on localhost. Optional LAN mode requires an administrator password hash and HTTPS. No Ollama, FastAPI or Next.js listener needs to bind to 0.0.0.0. Only the HTTPS gateway listens on a chosen private workstation address.

## 1. Configure the administrator

From the repository root, run:

```bash
.venv/bin/python scripts/password_hash.py
```

Enter a password of at least 12 characters, then paste the resulting STUDIO_ADMIN_PASSWORD_HASH line into .env. This is a scrypt hash; do not paste the plaintext password into any configuration. Dollar signs are literal in the dotenv file; do not source that file as a shell script.

Choose a LAN hostname, e.g. studio.home.arpa, and make it resolve to the workstation's private IP on each client (local DNS or a hosts entry). In .env set:

```dotenv
STUDIO_WEB_ORIGIN=https://studio.home.arpa
STUDIO_LAN_MODE=true
```

The exact HTTPS origin is required for browser mutation requests. Backend startup rejects LAN mode without HTTPS and a configured valid password hash. Session cookies are Secure, HttpOnly and SameSite=Strict in LAN mode; the session token is stored only as a SHA-256 digest in SQLite and expires after eight hours by default. Rotating the password hash invalidates prior browser sessions. API administrator tokens remain separately configurable.

## 2. Build and start

```bash
npm run build --prefix apps/web
./scripts/backend.sh --lan
# In a second terminal:
./scripts/web.sh --lan
```

Both services still bind to 127.0.0.1. web.sh uses production `next start` in LAN mode. Use one backend worker. Keep Ollama on localhost:11434. A saved provider endpoint in Settings takes precedence over STUDIO_OLLAMA_URL after restart.

## 3. Configure HTTPS

Install Caddy from its official distribution instructions. The supplied deploy/Caddyfile uses Caddy's local CA; each client must trust its root certificate. Configure the gateway process environment with your actual LAN hostname and private workstation IP, for example:

```bash
export STUDIO_LAN_ADDRESS=studio.home.arpa
export STUDIO_LAN_IP=192.168.1.50
caddy validate --config deploy/Caddyfile --adapter caddyfile
caddy run --config deploy/Caddyfile --adapter caddyfile
```

Binding port 443 may require your distribution's Caddy service/capability setup. For a system service, put these variables in its managed environment and install the config at its configured location. Never broadly grant shell or root access to the application. Do not edit your firewall automatically: if required, allow HTTPS only from your trusted LAN subnet. Do not port-forward the gateway through your router.

Caddy stores a local CA in its data directory. Install that CA certificate into every client's trust store using your OS/browser's certificate management. Do not bypass browser certificate warnings or distribute the CA private key. There is no cloud DNS, public certificate service or external authentication requirement. Automatic HTTP redirects are disabled so the provided config creates only the intended HTTPS listener. Streaming response flushing is enabled.

See [Caddy internal TLS](https://caddyserver.com/docs/caddyfile/directives/tls) and [reverse proxy configuration](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) for distribution-specific details.

## 4. Verify from a second device

Open https://studio.home.arpa. Private pages should redirect to /login; the backend also rejects protected API requests without a valid session or API administrator token. Sign in, verify a real streaming response, run a small benchmark, then sign out and confirm protected APIs become inaccessible. Test an expired session as well. Backend authorization is the security boundary; the Next.js proxy supplies the login redirect.

The initial release has one administrator identity and a local-mode principal, not multi-user accounts or a complete RBAC management system. All authenticated LAN users have administrator access. Failed login attempts are limited to five per minute for the backend-visible source address; browsers behind the same Next.js proxy share this bucket. Restarting the process resets this in-memory limit.

Actual Caddy configuration validation, TLS trust setup, second-device access and production browser/proxy behavior have not been verified in the agent sandbox. Complete these checks on the host before treating LAN mode as verified.
