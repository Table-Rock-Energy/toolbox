# Table Rock Tools — On-Prem Server Setup (`tre-serv-ai`)

**Scope:** operational reference for the on-prem staging deployment running on
`tre-serv-ai` (10.0.2.3). Reflects the actual setup as of April 2026.

**Companion docs:**
- `../README.md` → "Deployment" section: quick overview + cutover checklist.
- `../CLAUDE.md` → tech stack, code conventions, tool list.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Server Hardware & OS](#2-server-hardware--os)
3. [Local AI Stack (Ollama + LM Studio)](#3-local-ai-stack-ollama--lm-studio)
4. [Repo & Directory Layout](#4-repo--directory-layout)
5. [Docker Configuration](#5-docker-configuration)
6. [Application Deployment (docker-compose.prod.yml)](#6-application-deployment-docker-composeprodyml)
7. [Environment Variables](#7-environment-variables)
8. [Nginx — Containerized Reverse Proxy](#8-nginx--containerized-reverse-proxy)
9. [HTTPS / Let's Encrypt Cutover](#9-https--lets-encrypt-cutover)
10. [DNS & Remote Access](#10-dns--remote-access)
11. [Google Cloud Service Credentials](#11-google-cloud-service-credentials)
12. [Backups (TODO)](#12-backups-todo)
13. [Monitoring & Health Checks (partial)](#13-monitoring--health-checks-partial)
14. [Security Hardening](#14-security-hardening)
15. [Maintenance & Updates](#15-maintenance--updates)
16. [Port Reference](#16-port-reference)
17. [Troubleshooting](#17-troubleshooting)
18. [Setup Checklist](#18-setup-checklist)

---

## 1. Overview

The app runs in **two parallel deployments**:

- **Cloud Run (public)** — currently serves `tools.tablerocktx.com`. Auto-deployed from `main` by GitHub Actions.
- **On-prem staging (this box, `tre-serv-ai`)** — VPN / SSH access only. Tests and validates changes before public cutover; also hosts local LLM inference for the AI pipeline.

**Architecture on this box:**

```
                    VPN clients / SSH tunnel users
                                │
                      ┌─────────┴─────────┐
                      │  Host OS (Ubuntu) │
                      │                   │
                      │  :80  / :443 ─────┼──> toolbox-nginx (container)
                      │                   │        ↓ (docker bridge)
                      │                   │    toolbox-app (container)
                      │                   │        ↓                    ↓
                      │                   │    toolbox-db             host.docker.internal
                      │                   │    (PostgreSQL)                ↓
                      │                   │                           Ollama / LM Studio
                      │                   │                           (on host, dual L4 GPUs)
                      │                   │
                      └───────────────────┘
                                ↓ outbound HTTPS
                   Google Cloud (Firestore, GCS, Firebase Auth)
```

Docker network: `toolbox_default` bridge. The app reaches local LLMs via `host.docker.internal` (added as an `extra_hosts` entry in `docker-compose.prod.yml`).

---

## 2. Server Hardware & OS

| Item | Value |
|------|-------|
| Model | Dell PowerEdge R570 |
| CPU | Intel Xeon 6527P — 24 cores / 48 threads |
| RAM | 256 GB DDR5 ECC @ 6400 MHz (8× 32 GB; 8 DIMM slots free) |
| GPU | 2× NVIDIA L4 (24 GB VRAM each, 48 GB total) |
| NVMe | 447 GB Dell BOSS-N1 (OS) |
| RAID | 1.9 TB SAS, mounted at `/mnt/array` |
| Network | 2× 25 GbE + 4× 1 GbE |
| OS | Ubuntu 24.04.4 LTS (Noble Numbat) |
| Hostname | `tre-serv-ai` |
| Primary admin user | `table-rock-admin` |
| NVIDIA driver | `nvidia-driver-565-server`, CUDA 12.0 toolkit installed |
| Remote management | NinjaOne RMM agent |

Verify any of the above on the live box:

```bash
lscpu                 # CPU
free -h               # memory
nvidia-smi            # GPUs
lsblk -f              # disks
df -h                 # mount usage
cat /etc/os-release   # OS version
```

---

## 3. Local AI Stack (Ollama + LM Studio)

The app backend talks to local LLMs running **on the host OS** (not containerized), reached via `host.docker.internal`. Two runtimes are in use:

- **Ollama** — primary AI provider (commit `48c1a2a` switched from LM Studio). Serves an OpenAI-compatible API; the backend's AI service abstraction points at Ollama by default.
- **LM Studio** — secondary, useful for GUI model management, experiments, and serving alternate models. Runs on port 1234 by default.

Models currently on disk (`lms ls`):

- `qwen3.5-35b-a3b` (22 GB, Qwen 3.5 MoE — 35B total, 3B active)
- `qwen/qwen3.5-9b` (6.5 GB)
- `text-embedding-nomic-embed-text-v1.5` (84 MB)

Recommended LM Studio settings when loading the 35B model on one L4:

- Context Length: 16384 (can push to 32768 if VRAM allows)
- GPU Offload: 40 layers
- CPU Thread Pool Size: 24 (matches physical cores)
- Evaluation Batch Size: 512
- Max Concurrent Predictions: **1** (higher multiplies KV-cache VRAM per concurrent request)
- Flash Attention: On
- Unified KV Cache: On
- Offload KV Cache to GPU Memory: On

To change settings you must eject the model, adjust, then reload.

**Pinning models to specific GPUs:** LM Studio's LMLink doesn't expose per-GPU pinning. For explicit dual-GPU serving (35B on GPU 0, smaller model on GPU 1), use Ollama with `CUDA_VISIBLE_DEVICES=0` / `=1` in two processes on different ports.

---

## 4. Repo & Directory Layout

**Two-level layout on the server** — only the inner `app/` is a git repo:

```
/mnt/array/projects/toolbox/          # outer infra layer (NOT in git)
├── docker-compose.prod.yml           # production stack definition
├── nginx/default.conf                # copy of app/nginx/default.conf
├── .env                              # production secrets
└── app/                              # git: Table-Rock-Energy/toolbox.git
    ├── backend/                      # FastAPI
    ├── frontend/                     # React + Vite
    ├── Dockerfile                    # multi-stage (Node 20 → Python 3.11)
    ├── docker-compose.yml            # development (unused here)
    ├── nginx/default.conf            # canonical nginx config — edit here
    └── docs/SERVER_SETUP.md          # this file
```

**Rule:** edit `app/nginx/default.conf`, commit, push, then on the server
`cp app/nginx/default.conf nginx/default.conf` to sync the outer copy. The
outer file is what `docker-compose.prod.yml` bind-mounts into the nginx container.

Auxiliary paths:

```
/mnt/array/docker/        # Docker data-root (images, containers, volumes) — on RAID
/mnt/array/apps/          # reserved for other project stacks
/mnt/array/data/          # reserved for incoming / processed data
```

---

## 5. Docker Configuration

**Docker data-root is on the RAID array** to keep images and containers off the 100 GB NVMe root volume. The boot drive has enough headroom for the OS + GPU models; app containers live on the 1.8 TB RAID.

`/etc/docker/daemon.json`:

```json
{"data-root": "/mnt/array/docker"}
```

Verify:

```bash
docker info | grep "Docker Root Dir"
# → Docker Root Dir: /mnt/array/docker
```

Installed: Docker Engine 28.x + Docker Compose plugin (v2). Installed via `apt install docker.io docker-compose-v2` then migrated data-root per above.

---

## 6. Application Deployment (`docker-compose.prod.yml`)

All work runs from `/mnt/array/projects/toolbox/` (the outer layer). The compose file defines four services on the `toolbox_default` bridge:

| Service | Container | Image / Build | Port | Purpose |
|---------|-----------|---------------|------|---------|
| `app` | `toolbox-app` | `build: ./app` | expose :8080 (internal only) | FastAPI + built React SPA |
| `db` | `toolbox-db` | `postgres:16-alpine` | 127.0.0.1:5432 | PostgreSQL (currently disabled by env; primary DB is Firestore) |
| `nginx` | `toolbox-nginx` | `nginx:alpine` | 0.0.0.0:80, 0.0.0.0:443 | reverse proxy |
| `certbot` | `toolbox-certbot` | `certbot/certbot` | — | run on demand for ACME |

Key details baked into compose:

- `app` has `extra_hosts: ["host.docker.internal:host-gateway"]` so the backend can reach Ollama / LM Studio on the host.
- `nginx` bind-mounts `./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro`.
- `certbot_www` and `certbot_conf` named volumes are shared between nginx (read-only) and certbot (read-write) for ACME HTTP-01 and cert storage.
- `app_data` named volume persists uploaded files, the RRC CSVs, and the allowlist JSON at `/app/data` inside the container.

**Build + start the full stack:**

```bash
cd /mnt/array/projects/toolbox
docker compose -f docker-compose.prod.yml up -d --build
```

**Rebuild just the app** (after a code change to `app/`):

```bash
cd /mnt/array/projects/toolbox
git -C app pull
docker compose -f docker-compose.prod.yml up -d --build app
# brief 5–15 s window where nginx returns 502 until the new container is healthy
```

**Reload just nginx** (after a config change):

```bash
cd /mnt/array/projects/toolbox
cp app/nginx/default.conf nginx/default.conf
docker compose -f docker-compose.prod.yml exec nginx nginx -t
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

If the outer `nginx/default.conf` inode has drifted from the container's bind mount (can happen after `mv` / `rm` shenanigans), `nginx -s reload` will silently reload the old content. Fix by `docker compose restart nginx` to re-resolve the bind.

---

## 7. Environment Variables

Secrets live on the server at `/mnt/array/projects/toolbox/.env`. **Never commit this file.**

Expected contents (match `backend/app/core/config.py`):

```bash
# ── Application ─────────────────────────────────
ENVIRONMENT=production
DEBUG=false
PORT=8080

# ── Upload Limits ───────────────────────────────
MAX_UPLOAD_SIZE_MB=50

# ── Google Cloud Storage ────────────────────────
GCS_BUCKET_NAME=table-rock-tools-storage
GCS_PROJECT_ID=tablerockenergy

# ── Google Cloud Credentials ────────────────────
# Path inside the container; mount the JSON via a compose volume or
# docker secret if not baked into the image build.
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json

# ── Firestore (primary DB) ──────────────────────
FIRESTORE_ENABLED=true

# ── PostgreSQL (optional, disabled) ─────────────
DATABASE_ENABLED=false
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/toolbox
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<rotate-me>
POSTGRES_DB=toolbox

# ── Optional integrations (enable as needed) ────
GEMINI_API_KEY=...
GEMINI_ENABLED=false
GOOGLE_MAPS_API_KEY=...
GOOGLE_MAPS_ENABLED=false
PDL_API_KEY=...
SEARCHBUG_API_KEY=...
ENRICHMENT_ENABLED=false
ENCRYPTION_KEY=...       # Fernet key for GHL API key storage

# ── Local AI providers ──────────────────────────
# Ollama is the active provider (switched from LM Studio in commit 48c1a2a).
# The backend reaches the host via `host.docker.internal`.
# Set provider + endpoint in the admin settings UI, not env vars.
```

Permissions:

```bash
sudo chown table-rock-admin:table-rock-admin /mnt/array/projects/toolbox/.env
sudo chmod 600 /mnt/array/projects/toolbox/.env
```

---

## 8. Nginx — Containerized Reverse Proxy

`app/nginx/default.conf` is the canonical config. Today it serves **HTTP only**: the server is VPN-reachable via SSH tunnel and `tools.tablerocktx.com` DNS still points at Cloud Run, so no Let's Encrypt cert has been issued yet.

**Config contracts:**

- `proxy_pass http://app:8080` (docker service DNS). **Never** use `127.0.0.1:8080` inside the container — that's nginx's own loopback.
- `client_max_body_size 50M` on the catch-all matches backend `MAX_UPLOAD_SIZE_MB`.
- ACME challenge path (`/.well-known/acme-challenge/`) is always in place so a future certbot run works without config edits.

**Per-location timeout / streaming tuning:**

| Location | Timeout | Buffering | Rationale |
|----------|---------|-----------|-----------|
| `/api/pipeline/` | 600s | default | Ollama batches on 9B / 35B models can take minutes per request |
| `/api/ghl/send/` | 600s | off | SSE progress stream for bulk GHL contact send |
| `/api/proration/` | 300s | off | RRC downloads + NDJSON streaming from fetch-missing |
| `/api/revenue/` | 300s | off | Per-PDF progress ticks from multi-PDF upload |
| `/` catch-all | 120s | off | Frontend SPA + standard API |

An HTTPS `server { listen 443 ssl http2; ... }` block is present but commented
out in the config. See next section for how to activate it.

---

## 9. HTTPS / Let's Encrypt Cutover

To be done when we're ready to expose this box publicly — either on a staging
subdomain first, or a full `tools.tablerocktx.com` cutover from Cloud Run.

**Pre-checks:**

- Port 80 on the target hostname must be reachable from the public internet for ACME HTTP-01. If the box stays VPN-only, use DNS-01 instead (requires your DNS provider's API credentials).
- GCP service account + allowlist + any optional API keys must already be in `/mnt/array/projects/toolbox/.env`.

**Steps:**

1. **DNS** — point an A (or AAAA) record for the target hostname at this server's public IP. Confirm with `dig +trace <hostname>`.
2. **Update `server_name`** in `app/nginx/default.conf` from `_` to the target hostname. Commit + push + `git pull` on server + `cp app/nginx/default.conf nginx/default.conf` + `nginx -s reload`.
3. **Issue the cert** via the certbot sidecar:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm certbot certonly \
     --webroot -w /var/www/certbot \
     -d <hostname> \
     --email <contact> --agree-tos --no-eff-email
   ```
   Confirm: `docker compose exec nginx ls /etc/letsencrypt/live/<hostname>/`
4. **Enable the HTTPS server block** in `app/nginx/default.conf`:
   - Uncomment it, set `server_name` + cert paths to match.
   - Copy all `location` blocks (pipeline, ghl/send, proration, revenue, catch-all) from the HTTP server into the HTTPS server.
   - Replace the HTTP server body with a redirect: `return 301 https://$host$request_uri;` — but **keep** the `/.well-known/acme-challenge/` location so renewals work.
5. **Sync + reload**:
   ```bash
   cp app/nginx/default.conf nginx/default.conf
   docker compose -f docker-compose.prod.yml exec nginx nginx -t
   docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
   ```
6. **Auto-renewal** — add a cron or systemd timer for:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm certbot renew && \
     docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
   ```
7. **Verify:** `curl -v https://<hostname>/api/health` returns 200 with a valid chain. Browser-test the five tools.

**When taking Cloud Run down (full cutover):**

- Flip `tools.tablerocktx.com` DNS to this server's public IP; repeat steps 2–7 for that hostname.
- Disable `.github/workflows/deploy.yml` (or change its trigger) so merges stop deploying to Cloud Run.
- After at least one full day of stable on-prem operation: `gcloud run services delete table-rock-tools --region us-central1`.
- Keep the GCS bucket + Firestore project alive — the on-prem backend still depends on them unless/until we migrate to PostgreSQL + local storage.

---

## 10. DNS & Remote Access

### Current (staging)

- No public DNS to this box. `tools.tablerocktx.com` resolves to Cloud Run (`ghs.googlehosted.com`).
- Access from team members' Macs via SSH tunnel:
  ```bash
  ssh -L 8080:localhost:80 table-rock-admin@10.0.2.3
  # then open http://localhost:8080
  ```
- Internal IP: `10.0.2.3`. Admin SSH user: `table-rock-admin`.

### Options when exposing publicly

**A. WireGuard VPN** — lightweight, no inbound ports to the public, users connect via a VPN client before hitting the app.

**B. Corporate VPN** — if Table Rock adds a centralized VPN solution (Cisco AnyConnect, Fortinet, etc.), drop the server on the internal network and use split-horizon DNS.

**C. Cloudflare Tunnel** — no inbound ports needed, uses `cloudflared` outbound connection. Watch the 100s request cap on non-Enterprise plans — would break the AI pipeline and SSE streams. Only viable if long-request workloads are refactored to short request cycles.

### DNS records to plan for

| Record | Target | When |
|--------|--------|------|
| `staging.tablerocktx.com` A | server public IP | if we put staging online before full cutover |
| `tools.tablerocktx.com` A | server public IP | at full cutover; was previously Cloud Run |

---

## 11. Google Cloud Service Credentials

The app still uses Firebase Auth, Firestore, and GCS even when running on-prem.

Required roles on the service account (`tablerock-tools-onprem` in project `tablerockenergy`):

- Cloud Datastore User (Firestore read/write)
- Storage Object Admin (GCS)
- Firebase Authentication Admin (token verification)

**Key placement on the server:** mount the service-account JSON into the `toolbox-app` container as a volume, pointed at by `GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json`. Protect the file (600, owned by the admin user).

**Auth allowlist:** primary admin is `james@tablerocktx.com`. Allowlist stored inside the container at `/app/data/allowed_users.json` (persisted via the `app_data` named volume).

---

## 12. Backups (TODO)

Not yet configured. When we set this up, back up daily:

| Item | Location | Frequency |
|------|----------|-----------|
| Uploaded files / RRC CSVs | `app_data` volume | daily |
| `/app/data/allowed_users.json` | `app_data` volume | daily |
| `.env` | `/mnt/array/projects/toolbox/.env` | on change |
| GCP service account key | wherever mounted | on change |
| `app/nginx/default.conf` | git + outer copy | on change (covered by git) |
| Let's Encrypt certs | `certbot_conf` volume | on change |
| PostgreSQL (if enabled) | `pgdata` volume | daily |

Firestore data is backed up by Google Cloud automatically; no on-prem action needed for that.

A simple backup script example (not yet deployed):

```bash
#!/bin/bash
BACKUP_DIR=/mnt/array/backups/toolbox
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

# Volumes
docker run --rm -v toolbox_app_data:/src -v "$BACKUP_DIR":/dst alpine \
  tar -czf "/dst/app_data-$DATE.tar.gz" -C /src .
docker run --rm -v toolbox_certbot_conf:/src -v "$BACKUP_DIR":/dst alpine \
  tar -czf "/dst/certbot_conf-$DATE.tar.gz" -C /src .

# Env + server-local infra files
tar -czf "$BACKUP_DIR/infra-$DATE.tar.gz" \
  /mnt/array/projects/toolbox/.env \
  /mnt/array/projects/toolbox/nginx/default.conf \
  /mnt/array/projects/toolbox/docker-compose.prod.yml

# Retention: last 30
ls -t "$BACKUP_DIR"/*.tar.gz | tail -n +91 | xargs -r rm
```

Schedule with cron or systemd-timer once deployed.

---

## 13. Monitoring & Health Checks (partial)

**In place:**

- `toolbox-app` container health check: `curl -f http://localhost:8080/api/health` every 30s (defined in `Dockerfile`).
- `toolbox-db` Postgres health check: `pg_isready` every 10s (defined in compose).
- NinjaOne RMM agent on the host for server-level metrics.

**TODO:**

- Application-level alerting when the app goes unhealthy (NinjaOne can probably fire on service-health state).
- Log aggregation — currently logs live in each container (`docker logs -f toolbox-app`, `docker logs -f toolbox-nginx`).
- GPU monitoring for the Ollama / LM Studio workload (`nvidia-smi dmon` or DCGM exporter).

Quick operational commands:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
docker logs -f toolbox-app
docker logs -f toolbox-nginx
docker stats                                        # live CPU / mem per container
nvidia-smi                                          # GPU usage (Ollama / LM Studio)
curl http://localhost:80/api/health                 # via nginx
```

---

## 14. Security Hardening

### SSH

`/etc/ssh/sshd_config` recommended settings (verify on the box):

```
PermitRootLogin no
PasswordAuthentication no
MaxAuthTries 3
AllowUsers table-rock-admin
```

After changes: `sudo systemctl restart sshd`.

### UFW

The server sits behind the Table Rock network perimeter, so UFW isn't the primary firewall. Still, lock it down:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   comment "SSH"
sudo ufw allow 80/tcp   comment "HTTP (nginx container)"
sudo ufw allow 443/tcp  comment "HTTPS (nginx container, post-cutover)"
sudo ufw enable
```

### Fail2Ban

```bash
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban
```

### Docker

- No container publishes privileged ports to `0.0.0.0` except nginx (:80/:443).
- `toolbox-db` binds to `127.0.0.1:5432` only.
- GCP credentials mounted read-only.
- App runs as non-root (Python base image default user).

### Outbound allowlist

The server needs outbound HTTPS to:

| Destination | Purpose |
|-------------|---------|
| `*.googleapis.com` | Firestore, GCS, Firebase Auth |
| `*.firebaseio.com` | Firebase (if Realtime DB is ever used) |
| `webapps2.rrc.texas.gov` | RRC proration data downloads |
| `github.com` / `ghcr.io` | `git pull` + optional image pulls |
| `huggingface.co` | model downloads for Ollama / LM Studio |
| `ollama.com` | Ollama runtime + model pulls |

---

## 15. Maintenance & Updates

### Deploying app updates

```bash
cd /mnt/array/projects/toolbox/app
git pull
cd ..
# sync nginx if changed
cp app/nginx/default.conf nginx/default.conf
# rebuild + restart the app container only
docker compose -f docker-compose.prod.yml up -d --build app
# reload nginx if its config changed
docker compose -f docker-compose.prod.yml exec nginx nginx -t \
  && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
# verify
curl -sS http://localhost/api/health
```

### OS updates

```bash
sudo apt update && sudo apt upgrade -y
# reboot if kernel or drivers updated
sudo reboot
```

### Docker / disk reclamation

```bash
# images older than a week that aren't in use
docker image prune -a --filter "until=168h"
docker volume ls                                    # inspect before removing anything
docker system df                                    # usage summary
```

### LM Studio model management

Models live under `/home/table-rock-admin/.lmstudio/models/`. The CLI (`lms ls`, `lms get`, `lms load`, `lms unload`) lacks a `rm` verb; to free space:

```bash
rm -rf /home/table-rock-admin/.lmstudio/models/<publisher>/<model>/
# then restart LM Studio to refresh its index (the ghost listing is cosmetic)
```

---

## 16. Port Reference

| Port | Proto | Direction | Exposed by | Purpose |
|------|-------|-----------|------------|---------|
| 22 | TCP | in | host sshd | admin SSH |
| 80 | TCP | in | `toolbox-nginx` | HTTP (public + ACME challenge) |
| 443 | TCP | in | `toolbox-nginx` | HTTPS (after cutover) |
| 5432 | TCP | in (127.0.0.1) | `toolbox-db` | PostgreSQL (localhost-only) |
| 8080 | TCP | internal | `toolbox-app` | FastAPI (bridge-only, never host-exposed) |
| 1234 | TCP | internal | host LM Studio | LM Studio OpenAI-compatible API |
| 11434 | TCP | internal | host Ollama | Ollama API |

---

## 17. Troubleshooting

### `/api/*` returns 502 / 504 from nginx

- Check container: `docker ps --filter name=toolbox-app` — is it up and healthy?
- If "unhealthy", check logs: `docker logs toolbox-app --tail 100`. Common culprit: a long-running RRC county download blocked the event loop (fixed in commit `4f9b20b`; regressions elsewhere would look similar).
- Test upstream directly from inside nginx: `docker exec toolbox-nginx wget -qO- --timeout=5 http://app:8080/api/health`.

### Nginx config change didn't take effect

- Check the container actually sees the new content: `docker exec toolbox-nginx head /etc/nginx/conf.d/default.conf`.
- If it shows the old content, the bind-mount is on a stale inode (common after `mv` or symlink games). Fix: `docker compose -f docker-compose.prod.yml restart nginx`.

### Cannot reach the app at all

1. `docker ps` — are all containers Up?
2. `ss -tlnp | grep -E ':(80|443)'` — is nginx actually listening on the host?
3. `curl http://localhost/api/health` from the server itself — works?
4. SSH tunnel active (`ssh -L 8080:localhost:80 ...`) and forwarding the right port?

### Firebase Auth errors

- `GOOGLE_APPLICATION_CREDENTIALS` inside the container points at the mounted key?
- Service account has `Firebase Authentication Admin` role?
- System clock not drifting (JWT verification is time-sensitive): `timedatectl status`.

### RRC data download fails

- The RRC website uses outdated TLS. The app handles this with a custom SSL adapter (`RRCSSLAdapter` in `rrc_data_service.py`) — if you're running outside the app's code path, expect TLS errors.
- Confirm outbound access to `webapps2.rrc.texas.gov:443`.
- `/api/proration/rrc/fetch-missing` caps individual HTML queries to avoid rate-limiting; check `COUNTY_BUDGET_SECONDS` in `rrc_county_download_service.py`.

### Slow AI calls / Ollama timeouts

- `nvidia-smi` to see if the GPU is maxed. If both GPUs are idle but the request hangs, the model probably didn't load on GPU.
- Context-window overflow on LM Studio causes "death spiral" looping — bump context length in model load settings (see §3).

### Container won't start after a build

- `docker logs toolbox-app` — look for missing env var errors or DB connection failures.
- `.env` file present at `/mnt/array/projects/toolbox/.env` with `chmod 600`?
- Disk full? `df -h /mnt/array` — the RAID holds Docker data-root.

---

## 18. Setup Checklist

Treat this as a provisioning checklist for the next greenfield on-prem box (or a recovery scenario):

- [ ] Server hardware racked; Ubuntu 24.04 LTS installed + patched
- [ ] Admin user created, SSH key-only auth, root login disabled
- [ ] RAID array mounted at `/mnt/array`; `/mnt/array/docker` created for data-root
- [ ] NVIDIA driver + CUDA installed; `nvidia-smi` sees both GPUs
- [ ] Ollama + LM Studio installed; Qwen 35B and 9B pulled
- [ ] Docker Engine + compose v2 installed; data-root set to `/mnt/array/docker`
- [ ] Repo cloned at `/mnt/array/projects/toolbox/app`
- [ ] Outer `docker-compose.prod.yml` + `nginx/default.conf` + `.env` in place at `/mnt/array/projects/toolbox/`
- [ ] `.env` populated with GCS / Firestore / optional integration keys
- [ ] GCP service account JSON deployed and mounted into the `toolbox-app` container
- [ ] `docker compose -f docker-compose.prod.yml up -d --build` — all four containers healthy
- [ ] Health check passes: `curl http://localhost/api/health`
- [ ] SSH tunnel works from a team member's machine
- [ ] UFW + Fail2Ban enabled
- [ ] NinjaOne agent reporting
- [ ] Backup script staged (currently TODO)
- [ ] Cutover plan understood (DNS → certbot → HTTPS block → reload)
