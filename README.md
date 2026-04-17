# Table Rock Tools

Consolidated web application for Table Rock Energy's internal tools.

**Production URL** (public): https://tools.tablerocktx.com — hosted on Google Cloud Run

**On-prem staging**: `tre-serv-ai` (10.0.2.3) — internal / VPN access only. See [Deployment](#deployment) for layout.

## Tools

| Tool | Purpose |
|------|---------|
| **Extract** | Extract party/stakeholder info from OCC Exhibit A PDFs |
| **Title** | Consolidate owner/contact info from title opinions |
| **Proration** | Mineral holders + RRC queries + NRA calculations |
| **Revenue** | Extract revenue statements (EnergyLink/Energy Transfer) |
| **GHL Prep** | Transform Mineral export CSV for GoHighLevel import |

## Development

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker (optional)

### Quick Start

```bash
# Install dependencies
make install

# Run development servers
make dev
```

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### With Docker

```bash
make docker-up
```

## Deployment

The app currently runs in **two parallel deployments**:

### 1. Cloud Run (public)

Automatic deployment via GitHub Actions on push to `main` branch. This is what
`tools.tablerocktx.com` resolves to today.

- **GCP Project**: tablerockenergy
- **Service**: table-rock-tools
- **Region**: us-central1
- **Container**: built from `Dockerfile` (uvicorn on :8080, no nginx)

Manual deploy:

```bash
make deploy
```

### 2. On-prem staging — `tre-serv-ai` (10.0.2.3)

Dell PowerEdge R570 running Ubuntu 24.04 on-prem. VPN access only, plus the
server hosts local LLM inference (Ollama + LM Studio on two NVIDIA L4 GPUs)
that the backend talks to via `host.docker.internal`.

**Repo layout on the server is two-level** (only `app/` is in git; the outer
`toolbox/` layer is hand-maintained on the box):

```
/mnt/array/projects/toolbox/          # outer infra layer (NOT in git)
├── docker-compose.prod.yml           # app + db + nginx + certbot stack
├── nginx/default.conf                # copy of app/nginx/default.conf
├── .env                              # production secrets
└── app/                              # this repo (git: Table-Rock-Energy/toolbox)
    └── nginx/default.conf            # canonical nginx config — edit here
```

Keep the outer `nginx/default.conf` in sync with `app/nginx/default.conf`
whenever the in-repo copy changes.

**Container topology** (docker-compose.prod.yml):

| Service | Image / Build | Network | Notes |
|---------|---------------|---------|-------|
| `toolbox-app` | built from `./app/Dockerfile` | `toolbox_default` bridge | exposes :8080 internally; no host port |
| `toolbox-nginx` | `nginx:alpine` | `toolbox_default` bridge | publishes :80/:443 on host; proxies to `app:8080` via docker DNS |
| `toolbox-db` | `postgres:16-alpine` | `toolbox_default` bridge | data in `pgdata` named volume |
| `toolbox-certbot` | `certbot/certbot` | — | runs on demand for cert issuance/renewal |

**Key config hints:**

- Docker data-root lives on the 1.8 TB RAID array (`/mnt/array/docker`), not
  the NVMe boot drive. Set via `/etc/docker/daemon.json`.
- `nginx/default.conf` uses `proxy_pass http://app:8080` — the service name on
  the docker bridge. Do not use `127.0.0.1`; inside the nginx container that
  resolves to nginx itself, not the app.
- HTTPS is not yet enabled. The config ships as HTTP-only with the certbot
  ACME challenge path (`/.well-known/acme-challenge/`) in place. The HTTPS
  `server {}` block is present but commented out; uncomment after certbot has
  issued a certificate for whatever hostname points at this box.
- Per-endpoint timeouts in `nginx/default.conf`:
  - `/api/pipeline/` — 600s (long-running AI batches via Ollama)
  - `/api/ghl/send/` — 600s, no buffering (SSE progress stream)
  - `/api/proration/` — 300s, no buffering (RRC downloads + NDJSON)
  - `/api/revenue/` — 300s, no buffering (per-PDF streaming progress)
  - `/` catch-all — 120s, no buffering
- `client_max_body_size 50M` on the catch-all matches backend
  `MAX_UPLOAD_SIZE_MB`.

**Access for testing** (from a machine on the VPN):

```bash
ssh -L 8080:localhost:80 table-rock-admin@10.0.2.3
# then open http://localhost:8080 in your browser
```

**Building / deploying changes on the on-prem box:**

```bash
cd /mnt/array/projects/toolbox/app
git pull
cd ..
# sync nginx config if it changed
cp app/nginx/default.conf nginx/default.conf
# rebuild and restart app only (keeps nginx + db up)
docker compose -f docker-compose.prod.yml up -d --build app
# if nginx config changed:
docker compose -f docker-compose.prod.yml exec nginx nginx -t \
  && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### Cutover notes — when on-prem becomes public

These are the steps for whenever we promote the on-prem box to serve public
traffic (either a staging subdomain like `staging.tablerocktx.com` first, or
the full cutover of `tools.tablerocktx.com` off Cloud Run). Left as a
checklist so the context is here when we get there; nothing to do until then.

**Pre-checks:**

- Confirm the on-prem box has a public IP (or is fronted by one) reachable on
  ports 80 + 443 from the wider internet, not just the VPN. Certbot's HTTP-01
  challenge hits port 80 — if we stay VPN-only, use DNS-01 instead, which
  needs DNS provider API credentials.
- Confirm Firestore + GCS creds (`GOOGLE_APPLICATION_CREDENTIALS`) + any
  optional keys (Gemini, PDL, SearchBug, GHL encryption key) are in
  `/mnt/array/projects/toolbox/.env` on the server. Allowlist email for
  `james@tablerocktx.com` is in `app_data` volume at
  `/app/data/allowed_users.json` inside the container.
- Run full `make test` + `make preflight` locally and on the server beforehand.

**Cutover steps:**

1. **Pick hostname + point DNS.** Update DNS A record (or AAAA) for the
   target hostname to the server's public IP. Wait for propagation (use
   `dig +trace <hostname>`).
2. **Update `server_name` in the HTTP server block** of
   `app/nginx/default.conf` from `_` to the target hostname. Commit + push +
   `git pull` + `cp` to outer, `nginx -s reload`.
3. **Issue the certificate** via the certbot sidecar:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm certbot certonly \
     --webroot -w /var/www/certbot \
     -d <hostname> \
     --email <contact-email> --agree-tos --no-eff-email
   ```
   Confirm `/etc/letsencrypt/live/<hostname>/fullchain.pem` appears in the
   `certbot_conf` volume: `docker compose exec nginx ls /etc/letsencrypt/live/`.
4. **Enable the HTTPS server block** in `app/nginx/default.conf`:
   - Uncomment the `server { listen 443 ssl http2; ... }` block at the bottom.
   - Update `server_name` + `ssl_certificate` + `ssl_certificate_key` paths
     to match the issued hostname.
   - Copy all `location` blocks (proration, ghl/send, pipeline, revenue,
     catch-all `/`) from the HTTP server into the HTTPS server — same
     upstream, same timeouts.
   - Replace the HTTP server body with a single redirect:
     `return 301 https://$host$request_uri;` — but **keep** the
     `/.well-known/acme-challenge/` location so certbot renewal works.
5. **Sync + reload:**
   ```bash
   cp app/nginx/default.conf nginx/default.conf
   docker compose -f docker-compose.prod.yml exec nginx nginx -t
   docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
   ```
6. **Set up auto-renewal.** Either a host cron hitting
   `docker compose run --rm certbot renew` weekly, or a systemd timer. After
   renewal, `nginx -s reload` to pick up the new cert.
7. **Verify:** `curl -v https://<hostname>/api/health` returns 200 with a
   valid cert chain. Browser-test the five tools end-to-end.

**When taking Cloud Run down:**

- Flip `tools.tablerocktx.com` DNS from Google-hosted to the on-prem IP
  (repeat steps 1–7 above for that hostname, issuing a new cert alongside
  any staging cert).
- Disable the GitHub Actions workflow (`.github/workflows/deploy.yml`) or
  change its trigger so merges stop deploying to Cloud Run.
- `gcloud run services delete table-rock-tools --region us-central1` after
  at least one full day of on-prem operation, in case rollback is needed.
- Keep the GCS bucket + Firestore project alive — the on-prem backend still
  uses them unless we migrate those to PostgreSQL + local storage too.

## Project Structure

```
toolbox/
├── frontend/           # React + Vite + TypeScript
├── backend/            # FastAPI Python
├── .github/workflows/  # CI/CD
├── Dockerfile          # Production container
└── docker-compose.yml  # Local development
```

## License

Proprietary - Table Rock Energy
