# Linux workstation → HTTPS from a second PC

Use the native deployment for the existing workstation database/models. Docker remains an optional separate deployment and does not automatically import that database.

The user reported that the full verification, real model flows and manual browser use passed on the host. HTTPS/second-PC access and persistent services are the remaining acceptance steps. The agent sandbox cannot access LAN interfaces/systemd and does not have Caddy installed, so it cannot perform these host actions itself.

## 1. Linux prerequisites

Find the workstation's actual RFC1918 LAN IPv4 with `hostname -I` or `ip -brief -4 address`. Use its Wi-Fi/Ethernet address, not a Docker, VPN or localhost address. Prefer a DHCP reservation so the address stays stable.

Install Caddy using the [official Ubuntu/Debian instructions](https://caddyserver.com/docs/install#debian-ubuntu-raspbian). If the package enables a default system Caddy server that you do not use for other sites, disable that unused service (`sudo systemctl disable --now caddy`); the installer does not alter existing system-level web servers. Confirm `caddy version` and `systemctl --user status` work in your normal desktop terminal. Node/npm must be in that terminal's PATH; the installer captures that PATH in the generated user services, including fnm installations.

Stop the manually running backend and web terminals with Ctrl+C before applying services. The installer refuses to kill unmanaged processes occupying ports 8000/3000. Ollama should keep running normally on localhost:11434.

## 2. Prepare or apply

From the repository root, replacing the example address with the real one:

```bash
# Optional preview: only writes private generated files inside the project.
.venv/bin/python scripts/deploy_lan.py --address 192.168.1.50

# Actual host install: run in your normal Linux terminal, not as root.
.venv/bin/python scripts/deploy_lan.py --address 192.168.1.50 --apply
```

The example IP is not an automatically selected address. The default gateway port is 8443; a different unused unprivileged port can be supplied with --port. No hosts/DNS entries, sudo port binding, public certificate service or internet exposure are required for the IP URL. Caddy can serve IP addresses using its local CA. [Caddy HTTPS behavior](https://caddyserver.com/docs/automatic-https).

The installer:

- Validates private IPv4/port, Caddy/Node/npm, user systemd access and unmanaged listeners before modifying configuration.
- Reuses an existing password hash; otherwise prompts for a new administrator password locally. No password is printed or sent to chat.
- Builds the production frontend before changing services/.env.
- Backs up .env and existing service units privately, and creates a consistent SQLite backup with SQLite's backup API.
- Preserves other .env settings, database location and secrets; sets only HTTPS origin, LAN mode and the password hash if needed.
- Generates three user units with absolute project paths and the current Node PATH: backend, web and HTTPS gateway. Enables/restarts them with restrictive file permissions.
- Keeps FastAPI/Next.js/Ollama on localhost. Only Caddy binds the supplied private IP on 8443, without an admin endpoint or automatic HTTP listener.
- Verifies the actual TLS certificate, anonymous API denial and page redirect, then exports **only the public CA certificate** plus SHA-256 fingerprints.

Backups are in data/backups/ (private). Generated config/profile/public certificate are in deploy/generated/lan/ (gitignored). The CA private key stays in data/lan-gateway/; do not transfer that directory to clients.

If the script fails, read the reported stage. Preflight/build failure does not change .env or services. A later service failure may leave installed configuration: inspect logs and the generated files; it is not reported as successful. No trust store, firewall or linger policy is modified automatically.

## 3. Verify services and public CA

```bash
systemctl --user status local-llm-studio-backend local-llm-studio-web local-llm-studio-gateway
journalctl --user -u local-llm-studio-backend -u local-llm-studio-web -u local-llm-studio-gateway -n 100 --no-pager
.venv/bin/python scripts/deploy_lan.py --address 192.168.1.50 --check
```

The browser URL is `https://192.168.1.50:8443`. Transfer `deploy/generated/lan/studio-lan-root.crt` to the second PC through a trusted file transfer. Compare its file SHA-256 against the **CA file SHA-256** printed on Linux. Do not compare a file digest to the separately printed certificate DER fingerprint.

Windows file verification and current-user certificate import (normal PowerShell):

```powershell
certutil -hashfile .\studio-lan-root.crt SHA256
certutil -user -addstore Root .\studio-lan-root.crt
```

Chrome/Edge use the Windows certificate trust configuration. For a browser with a separate authority store, import this public certificate into its Authorities section and trust it for website identification. Do not bypass a certificate warning.

Ubuntu/Debian clients can compare `sha256sum studio-lan-root.crt`, then install the public certificate into the local CA store with `sudo install -m 0644 studio-lan-root.crt /usr/local/share/ca-certificates/studio-lan-root.crt` and `sudo update-ca-certificates`. A browser with its own store may also need the Authorities import. On macOS, compare `shasum -a 256 studio-lan-root.crt` and use Keychain Access to import/trust that certificate for SSL.

If the Linux host's firewall blocks the second PC, allow **TCP 8443 from that specific PC's IP** using your firewall's normal configuration. For UFW, review `sudo ufw status`, then use `sudo ufw allow from <second-PC-IP> to <workstation-IP> port 8443 proto tcp`. No broad public allow or router forwarding is needed. The installer intentionally does not guess client IPs or change firewall rules.

## 4. Second-PC acceptance

1. Open the printed HTTPS URL. Confirm there is no certificate warning and that /chat redirects to /login before authentication.
2. Sign in with the administrator password chosen on Linux. Verify installed models and send a short message; execution must happen on the workstation.
3. Stop generation, reload the conversation and open Monitoring. Run a small benchmark while avoiding other Ollama work.
4. Sign out; protected pages should redirect and /api/conversations should return 401. Check an expired session as well.
5. Restart the Linux app services and confirm saved conversations remain. User services start with the user manager. To run while logged out/at boot, review your distribution's linger policy (`loginctl enable-linger <Linux-user>` may require administrator permission); it is not enabled automatically.

All LAN users currently sign in as the single administrator. Keep the gateway on the trusted local network. Existing API administrator tokens remain valid independently of password sessions.

## Back out of LAN mode

Stop/disable the gateway unit with `systemctl --user disable --now local-llm-studio-gateway`. Set STUDIO_LAN_MODE=false and STUDIO_WEB_ORIGIN=http://127.0.0.1:3000 in .env, preserving other values, then restart backend/web services. Restore backed-up unit files if replacing an earlier setup and run `systemctl --user daemon-reload`. Do not restore the SQLite backup over newer conversations unless you explicitly intend to discard later data. Client CA trust can be removed from the same certificate store used to import it.

The generated installer is unit-tested, but real Caddy validation, systemd activation and the second-PC test remain pending until executed on the host.
