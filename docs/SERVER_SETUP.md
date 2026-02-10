# Table Rock Tools - On-Premises Server Setup Guide

**Prepared for:** CTO / IT Infrastructure
**Application:** Table Rock TX Toolbox
**Last Updated:** February 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [VM Specifications](#2-vm-specifications)
3. [OS Installation & Base Configuration](#3-os-installation--base-configuration)
4. [Runtime Dependencies](#4-runtime-dependencies)
5. [Application Deployment (Docker)](#5-application-deployment-docker)
6. [Application Deployment (Bare Metal Alternative)](#6-application-deployment-bare-metal-alternative)
7. [Reverse Proxy & SSL](#7-reverse-proxy--ssl)
8. [Firewall Configuration](#8-firewall-configuration)
9. [VPN / Remote Access](#9-vpn--remote-access)
10. [DNS Configuration](#10-dns-configuration)
11. [Google Cloud Service Credentials](#11-google-cloud-service-credentials)
12. [Environment Variables](#12-environment-variables)
13. [Systemd Service Configuration](#13-systemd-service-configuration)
14. [Backup Strategy](#14-backup-strategy)
15. [Monitoring & Health Checks](#15-monitoring--health-checks)
16. [Security Hardening](#16-security-hardening)
17. [Maintenance & Updates](#17-maintenance--updates)
18. [Appendix: Port Reference](#18-appendix-port-reference)
19. [Appendix: Troubleshooting](#19-appendix-troubleshooting)

---

## 1. Overview

Table Rock Tools is a web application used by the land and revenue teams for document processing (PDF extraction, title opinions, proration calculations, revenue parsing). It consists of:

- **Frontend:** React single-page application (built to static files, served by the backend)
- **Backend:** Python FastAPI server (handles API requests, PDF processing, data pipelines)
- **External Dependencies:** Firebase Auth (Google-hosted), Firestore (Google-hosted), Google Cloud Storage (file storage)

The application is currently deployed to Google Cloud Run. This document covers migrating it to a dedicated on-premises virtual machine while maintaining connectivity to Google Cloud services (Firebase Auth, Firestore, GCS) until those can also be migrated.

### Architecture Diagram

```
                    Internet
                       │
                ┌──────┴──────┐
                │   Firewall  │
                │  (port 443) │
                └──────┬──────┘
                       │
              ┌────────┴────────┐
              │  Nginx Reverse  │
              │  Proxy + SSL    │
              │  (port 443→8080)│
              └────────┬────────┘
                       │
              ┌────────┴────────┐
              │  Docker Engine  │
              │                 │
              │  ┌────────────┐ │
              │  │ Toolbox    │ │      ┌─────────────────┐
              │  │ Container  │─┼─────>│ Google Cloud     │
              │  │ (port 8080)│ │      │ - Firebase Auth  │
              │  └────────────┘ │      │ - Firestore      │
              │                 │      │ - GCS Bucket     │
              └─────────────────┘      └─────────────────┘
```

---

## 2. VM Specifications

### Minimum Requirements

| Resource   | Minimum     | Recommended   | Notes                                            |
|------------|-------------|---------------|--------------------------------------------------|
| CPU        | 2 vCPU      | 4 vCPU        | PDF processing is CPU-intensive                  |
| RAM        | 4 GB        | 8 GB          | Pandas DataFrames for RRC data cached in memory  |
| Disk       | 40 GB SSD   | 80 GB SSD     | OS + Docker images + uploaded files + RRC CSVs   |
| Network    | 100 Mbps    | 1 Gbps        | File uploads up to 50 MB each                    |

### Disk Layout Recommendation

| Mount Point        | Size   | Purpose                                      |
|--------------------|--------|----------------------------------------------|
| `/`                | 20 GB  | OS + packages                                |
| `/var/lib/docker`  | 20 GB  | Docker images and containers                 |
| `/opt/tablerock`   | 20 GB  | Application data, uploads, RRC CSVs, backups |

### OS

**Ubuntu Server 22.04 LTS** (recommended) or **24.04 LTS**

Other supported options: Debian 12, RHEL 9, Rocky Linux 9. The instructions below assume Ubuntu/Debian.

---

## 3. OS Installation & Base Configuration

### 3.1 Initial Setup

After installing Ubuntu Server, perform initial configuration:

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Set timezone (adjust to your location)
sudo timedatectl set-timezone America/Chicago

# Set hostname
sudo hostnamectl set-hostname tablerock-tools

# Install essential packages
sudo apt install -y \
    curl \
    wget \
    git \
    ufw \
    fail2ban \
    unattended-upgrades \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    htop \
    vim
```

### 3.2 Create Application User

```bash
# Create a dedicated service user (no login shell)
sudo useradd -r -m -d /opt/tablerock -s /usr/sbin/nologin tablerock

# Create application directories
sudo mkdir -p /opt/tablerock/{app,data,backups,certs,logs}
sudo chown -R tablerock:tablerock /opt/tablerock
```

### 3.3 Enable Automatic Security Updates

```bash
sudo dpkg-reconfigure -plow unattended-upgrades
# Select "Yes" to enable automatic security updates
```

---

## 4. Runtime Dependencies

### 4.1 Docker Engine (Recommended Deployment Method)

Docker is the recommended way to run the application. It packages all dependencies (Python, Node build artifacts, system libraries like Tesseract and Poppler) into a single container.

```bash
# Add Docker's official GPG key and repository
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Verify installation
sudo docker run hello-world
```

### 4.2 Bare Metal Dependencies (Alternative - Only If Not Using Docker)

If running without Docker, install these directly on the VM:

```bash
# Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Node.js 20 (for building frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# System libraries required by the backend
sudo apt install -y \
    poppler-utils \       # PDF rendering (pdf2image)
    tesseract-ocr \       # OCR for scanned PDFs
    build-essential \     # C compiler for Python packages
    libpq-dev             # PostgreSQL client library (if using PostgreSQL)
```

---

## 5. Application Deployment (Docker)

This is the **recommended** deployment method.

### 5.1 Clone the Repository

```bash
# Clone to the application directory
sudo -u tablerock git clone <REPO_URL> /opt/tablerock/app
cd /opt/tablerock/app/toolbox
```

### 5.2 Build the Docker Image

The multi-stage Dockerfile handles everything:
- Stage 1: Builds the React frontend using Node 20
- Stage 2: Installs Python 3.11, system libraries (Tesseract, Poppler), Python packages, and copies the built frontend

```bash
cd /opt/tablerock/app/toolbox
sudo docker build -t tablerock-tools:latest .
```

### 5.3 Prepare Data Volume

```bash
# Create persistent data directory for uploads, RRC CSVs, and allowlist
sudo mkdir -p /opt/tablerock/data
sudo chown -R tablerock:tablerock /opt/tablerock/data
```

### 5.4 Create the Environment File

```bash
sudo -u tablerock vim /opt/tablerock/.env
```

See [Section 12: Environment Variables](#12-environment-variables) for full contents.

### 5.5 Run the Container

```bash
sudo docker run -d \
    --name tablerock-tools \
    --restart unless-stopped \
    --env-file /opt/tablerock/.env \
    -p 127.0.0.1:8080:8080 \
    -v /opt/tablerock/data:/app/data \
    -v /opt/tablerock/certs/gcp-service-account.json:/app/credentials.json:ro \
    tablerock-tools:latest
```

Key flags:
- `--restart unless-stopped` ensures the container restarts on crash or server reboot
- `-p 127.0.0.1:8080:8080` binds ONLY to localhost (Nginx will proxy external traffic)
- `-v /opt/tablerock/data:/app/data` persists uploaded files and RRC data across restarts
- The GCP credentials file is mounted read-only

### 5.6 Verify

```bash
# Check container is running
sudo docker ps

# Check health endpoint
curl http://localhost:8080/api/health

# Expected response:
# {"status":"healthy","service":"table-rock-toolbox","version":"1.0.0","tools":["extract","title","proration","revenue"]}

# View logs
sudo docker logs -f tablerock-tools
```

---

## 6. Application Deployment (Bare Metal Alternative)

Only use this if Docker is not an option.

### 6.1 Set Up Python Virtual Environment

```bash
cd /opt/tablerock/app/toolbox

# Create virtual environment
python3.11 -m venv /opt/tablerock/venv

# Activate and install dependencies
source /opt/tablerock/venv/bin/activate
pip install -r backend/requirements.txt
```

### 6.2 Build the Frontend

```bash
cd /opt/tablerock/app/toolbox/frontend
npm ci
npm run build

# Copy built files to where the backend expects them
cp -r dist /opt/tablerock/app/toolbox/backend/static
```

### 6.3 Run with Uvicorn

```bash
cd /opt/tablerock/app/toolbox/backend
/opt/tablerock/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 2
```

For production, use the systemd service in [Section 13](#13-systemd-service-configuration).

---

## 7. Reverse Proxy & SSL

Use Nginx as a reverse proxy to handle HTTPS termination and forward requests to the application container.

### 7.1 Install Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
```

### 7.2 SSL Certificate

**Option A: Let's Encrypt (if the server is publicly reachable)**

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tools.tablerocktx.com
```

**Option B: Self-signed or internal CA (for VPN-only access)**

```bash
# Generate a self-signed cert (replace with your internal CA cert if available)
sudo openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout /opt/tablerock/certs/server.key \
    -out /opt/tablerock/certs/server.crt \
    -subj "/CN=tools.tablerocktx.com/O=Table Rock Energy"
```

**Option C: Purchased/corporate wildcard certificate**

Place the cert and key files at:
- `/opt/tablerock/certs/server.crt`
- `/opt/tablerock/certs/server.key`

### 7.3 Nginx Configuration

Create `/etc/nginx/sites-available/tablerock-tools`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name tools.tablerocktx.com;
    return 301 https://$host$request_uri;
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    server_name tools.tablerocktx.com;

    # SSL certificates (adjust paths based on your choice above)
    ssl_certificate     /opt/tablerock/certs/server.crt;
    ssl_certificate_key /opt/tablerock/certs/server.key;

    # SSL hardening
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # File upload size limit (matches backend MAX_UPLOAD_SIZE_MB)
    client_max_body_size 50M;

    # Proxy to application container
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout for long PDF processing requests
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # Logging
    access_log /opt/tablerock/logs/nginx-access.log;
    error_log  /opt/tablerock/logs/nginx-error.log;
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/tablerock-tools /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

---

## 8. Firewall Configuration

### 8.1 UFW Rules

```bash
# Enable UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (adjust port if you change the default)
sudo ufw allow 22/tcp comment "SSH"

# Allow HTTPS (public or VPN traffic)
sudo ufw allow 443/tcp comment "HTTPS - Table Rock Tools"

# Allow HTTP only for Let's Encrypt redirect (optional)
sudo ufw allow 80/tcp comment "HTTP - redirect to HTTPS"

# If using WireGuard VPN on this server
sudo ufw allow 51820/udp comment "WireGuard VPN"

# Enable firewall
sudo ufw enable
sudo ufw status verbose
```

### 8.2 Outbound Requirements

The server needs outbound HTTPS access to the following Google Cloud endpoints:

| Destination                          | Port | Purpose                          |
|--------------------------------------|------|----------------------------------|
| `*.googleapis.com`                   | 443  | Firestore, GCS, Firebase Auth    |
| `*.firebaseio.com`                   | 443  | Firebase Realtime (if used)      |
| `webapps2.rrc.texas.gov`            | 443  | RRC proration data downloads     |
| `github.com` / `ghcr.io`           | 443  | Git pulls for updates (optional) |

If your on-prem firewall restricts outbound traffic, these must be allowlisted.

---

## 9. VPN / Remote Access

The toolbox is an internal application. Users need secure remote access to reach the server. There are several options depending on existing infrastructure.

### Option A: WireGuard VPN (Recommended for Simplicity)

WireGuard is lightweight, fast, and easy to configure. Users install the WireGuard client on their devices and connect to the server's VPN before accessing the web app.

**Install on the server:**

```bash
sudo apt install -y wireguard

# Generate server keys
wg genkey | sudo tee /etc/wireguard/server_private.key | wg pubkey | sudo tee /etc/wireguard/server_public.key
sudo chmod 600 /etc/wireguard/server_private.key
```

**Server config** (`/etc/wireguard/wg0.conf`):

```ini
[Interface]
Address = 10.10.0.1/24
ListenPort = 51820
PrivateKey = <SERVER_PRIVATE_KEY>

# Enable IP forwarding for VPN clients
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

# Client: James
[Peer]
PublicKey = <CLIENT_PUBLIC_KEY>
AllowedIPs = 10.10.0.2/32
```

**Start the VPN:**

```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
```

**Client config** (distributed to each user):

```ini
[Interface]
Address = 10.10.0.2/24
PrivateKey = <CLIENT_PRIVATE_KEY>
DNS = 1.1.1.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = <SERVER_PUBLIC_IP>:51820
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
```

With this setup, users connect via VPN and access `https://tools.tablerocktx.com` (or `https://10.10.0.1`) in their browser.

### Option B: Existing Corporate VPN

If Table Rock already has a VPN solution (e.g., Cisco AnyConnect, OpenVPN, Fortinet), simply:

1. Place the tools server on the internal network
2. Ensure VPN clients can reach the server on port 443
3. Add a DNS entry (internal or split-horizon) for `tools.tablerocktx.com` pointing to the server's internal IP

### Option C: Cloudflare Tunnel (Zero-Trust, No Inbound Ports)

If you don't want to open any inbound ports or manage VPN clients:

```bash
# Install cloudflared
curl -fsSL https://pkg.cloudflare.com/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Authenticate and create tunnel
cloudflared tunnel login
cloudflared tunnel create tablerock-tools
cloudflared tunnel route dns tablerock-tools tools.tablerocktx.com
```

Cloudflare Access policies can restrict who can reach the app (by email domain, etc.) without a VPN client.

---

## 10. DNS Configuration

The application currently lives at `tools.tablerocktx.com`. You'll need to update DNS to point to the on-prem server instead of Cloud Run.

### If Using VPN-Only Access

Add an internal DNS record (or `/etc/hosts` entries on client machines):

```
tools.tablerocktx.com    A    10.10.0.1     # WireGuard VPN IP of server
```

### If Server Has a Public IP

Update the DNS A record at your registrar:

```
tools.tablerocktx.com    A    <SERVER_PUBLIC_IP>
```

### Split-Horizon DNS (Best of Both)

- Internal DNS resolves `tools.tablerocktx.com` to the server's private/VPN IP
- External DNS either doesn't resolve it (VPN-only) or points to the public IP

---

## 11. Google Cloud Service Credentials

The application connects to Google Cloud services (Firestore, GCS, Firebase Auth). These will continue running in Google Cloud even after the server moves on-prem. A service account key file is required.

### 11.1 Create a Service Account

In the Google Cloud Console (`console.cloud.google.com`), project `tablerockenergy`:

1. Go to **IAM & Admin > Service Accounts**
2. Click **Create Service Account**
   - Name: `tablerock-tools-onprem`
   - ID: `tablerock-tools-onprem`
3. Grant roles:
   - `Cloud Datastore User` (Firestore read/write)
   - `Storage Object Admin` (GCS read/write)
   - `Firebase Authentication Admin` (token verification)
4. Click **Done**
5. Click into the service account > **Keys** > **Add Key** > **Create New Key** > **JSON**
6. Download the JSON key file

### 11.2 Deploy the Key to the Server

```bash
# Copy the key file to the server securely
scp tablerockenergy-sa-key.json user@server:/tmp/

# Move to the certs directory with restricted permissions
sudo mv /tmp/tablerockenergy-sa-key.json /opt/tablerock/certs/gcp-service-account.json
sudo chown tablerock:tablerock /opt/tablerock/certs/gcp-service-account.json
sudo chmod 600 /opt/tablerock/certs/gcp-service-account.json
```

The Docker container mounts this file read-only (see Section 5.5).

---

## 12. Environment Variables

Create `/opt/tablerock/.env`:

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
# Path INSIDE the container (mapped via Docker volume)
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json

# ── Firestore ───────────────────────────────────
FIRESTORE_ENABLED=true

# ── PostgreSQL (optional, disabled by default) ──
DATABASE_ENABLED=false
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox
```

Restrict permissions:

```bash
sudo chown tablerock:tablerock /opt/tablerock/.env
sudo chmod 600 /opt/tablerock/.env
```

---

## 13. Systemd Service Configuration

### 13.1 Docker-Based Service

Create `/etc/systemd/system/tablerock-tools.service`:

```ini
[Unit]
Description=Table Rock Tools (Docker)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=simple
Restart=always
RestartSec=10
User=root

ExecStartPre=-/usr/bin/docker stop tablerock-tools
ExecStartPre=-/usr/bin/docker rm tablerock-tools

ExecStart=/usr/bin/docker run \
    --name tablerock-tools \
    --env-file /opt/tablerock/.env \
    -p 127.0.0.1:8080:8080 \
    -v /opt/tablerock/data:/app/data \
    -v /opt/tablerock/certs/gcp-service-account.json:/app/credentials.json:ro \
    tablerock-tools:latest

ExecStop=/usr/bin/docker stop tablerock-tools

[Install]
WantedBy=multi-user.target
```

### 13.2 Bare Metal Service (Alternative)

If not using Docker, create `/etc/systemd/system/tablerock-tools.service`:

```ini
[Unit]
Description=Table Rock Tools (Uvicorn)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=tablerock
Group=tablerock
WorkingDirectory=/opt/tablerock/app/toolbox/backend
Environment="PATH=/opt/tablerock/venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=/opt/tablerock/.env
ExecStart=/opt/tablerock/venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8080 \
    --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 13.3 Enable the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable tablerock-tools
sudo systemctl start tablerock-tools

# Verify
sudo systemctl status tablerock-tools
```

---

## 14. Backup Strategy

### 14.1 What to Back Up

| Item                                   | Location on Server                            | Frequency |
|----------------------------------------|-----------------------------------------------|-----------|
| Uploaded files & RRC CSVs              | `/opt/tablerock/data/`                        | Daily     |
| User allowlist                         | `/opt/tablerock/data/allowed_users.json`      | Daily     |
| Environment config                     | `/opt/tablerock/.env`                         | On change |
| GCP service account key                | `/opt/tablerock/certs/gcp-service-account.json` | On change |
| Nginx config                           | `/etc/nginx/sites-available/tablerock-tools`  | On change |
| SSL certificates                       | `/opt/tablerock/certs/`                       | On change |

Firestore data is backed up by Google Cloud automatically.

### 14.2 Simple Backup Script

Create `/opt/tablerock/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/tablerock/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/tablerock-$DATE.tar.gz"

tar -czf "$DEST" \
    /opt/tablerock/data \
    /opt/tablerock/.env \
    /opt/tablerock/certs \
    /etc/nginx/sites-available/tablerock-tools

# Keep only the last 30 backups
ls -t "$BACKUP_DIR"/tablerock-*.tar.gz | tail -n +31 | xargs -r rm

echo "Backup created: $DEST"
```

```bash
sudo chmod +x /opt/tablerock/backup.sh

# Schedule daily backup at 3 AM via cron
echo "0 3 * * * /opt/tablerock/backup.sh" | sudo crontab -u tablerock -
```

---

## 15. Monitoring & Health Checks

### 15.1 Application Health

The app exposes a health endpoint:

```bash
curl -s http://localhost:8080/api/health | python3 -m json.tool
```

### 15.2 Simple Monitoring Script

Create `/opt/tablerock/healthcheck.sh`:

```bash
#!/bin/bash
HEALTH=$(curl -sf http://localhost:8080/api/health)
if [ $? -ne 0 ]; then
    echo "$(date): Health check FAILED - restarting service" >> /opt/tablerock/logs/healthcheck.log
    systemctl restart tablerock-tools
else
    echo "$(date): OK" >> /opt/tablerock/logs/healthcheck.log
fi
```

```bash
# Run every 5 minutes
echo "*/5 * * * * /opt/tablerock/healthcheck.sh" | sudo crontab -u root -
```

### 15.3 Log Monitoring

```bash
# Application logs (Docker)
sudo docker logs -f tablerock-tools

# Nginx logs
tail -f /opt/tablerock/logs/nginx-access.log
tail -f /opt/tablerock/logs/nginx-error.log
```

---

## 16. Security Hardening

### 16.1 SSH Hardening

Edit `/etc/ssh/sshd_config`:

```
PermitRootLogin no
PasswordAuthentication no      # Use SSH keys only
MaxAuthTries 3
AllowUsers <your-admin-user>   # Restrict SSH to specific users
```

```bash
sudo systemctl restart sshd
```

### 16.2 Fail2Ban

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 16.3 Docker Security

- The container runs on port 8080 bound to `127.0.0.1` only (not exposed to the network directly)
- All external traffic goes through Nginx with SSL
- The GCP credentials file is mounted read-only
- The application container does not run as root by default (Python base image)

---

## 17. Maintenance & Updates

### 17.1 Deploying Application Updates

```bash
cd /opt/tablerock/app

# Pull latest code
sudo -u tablerock git pull origin main

# Rebuild the Docker image
cd toolbox
sudo docker build -t tablerock-tools:latest .

# Restart the service (brief downtime)
sudo systemctl restart tablerock-tools

# Verify health
sleep 10
curl -s http://localhost:8080/api/health
```

### 17.2 OS Updates

```bash
sudo apt update && sudo apt upgrade -y
# Reboot if kernel was updated
sudo reboot
```

### 17.3 Docker Cleanup

```bash
# Remove unused images (reclaim disk)
sudo docker image prune -a --filter "until=168h"
```

---

## 18. Appendix: Port Reference

| Port  | Protocol | Direction | Service              | Exposed To     |
|-------|----------|-----------|----------------------|----------------|
| 22    | TCP      | Inbound   | SSH                  | Admin only     |
| 80    | TCP      | Inbound   | HTTP (redirect)      | All/VPN        |
| 443   | TCP      | Inbound   | HTTPS (Nginx)        | All/VPN        |
| 8080  | TCP      | Internal  | App container        | localhost only |
| 51820 | UDP      | Inbound   | WireGuard VPN        | All (if used)  |

---

## 19. Appendix: Troubleshooting

### Container won't start

```bash
# Check Docker logs
sudo docker logs tablerock-tools

# Common issues:
# - Missing .env file or credentials
# - Port 8080 already in use
# - Insufficient disk space
```

### Cannot reach the app from the browser

1. Verify the container is running: `sudo docker ps`
2. Verify Nginx is running: `sudo systemctl status nginx`
3. Test locally: `curl http://localhost:8080/api/health`
4. Test Nginx: `curl -k https://localhost/api/health`
5. Check firewall: `sudo ufw status`
6. If using VPN: verify VPN is connected and the client can ping the server

### Firebase Auth errors

- Verify the GCP service account key is mounted correctly
- Verify `GOOGLE_APPLICATION_CREDENTIALS` points to the correct path inside the container
- Check that the service account has the `Firebase Authentication Admin` role

### RRC data download fails

- The RRC website uses outdated SSL. The application handles this internally with a custom SSL adapter.
- Verify outbound HTTPS access to `webapps2.rrc.texas.gov` is allowed through the firewall.

### Slow PDF processing

- PDF extraction is CPU-bound. If processing is slow, allocate more vCPUs to the VM.
- Check RAM usage with `htop` -- if pandas DataFrames are consuming too much memory, increase VM RAM.

---

## Setup Checklist

Use this checklist when provisioning the server:

- [ ] VM created with recommended specs (4 vCPU, 8 GB RAM, 80 GB SSD)
- [ ] Ubuntu 22.04 LTS installed and updated
- [ ] Docker Engine installed and running
- [ ] Application cloned and Docker image built
- [ ] GCP service account key deployed to `/opt/tablerock/certs/`
- [ ] Environment file created at `/opt/tablerock/.env`
- [ ] Application container running and health check passing
- [ ] Nginx installed with SSL certificate configured
- [ ] UFW firewall enabled with correct rules
- [ ] VPN configured (WireGuard, corporate VPN, or Cloudflare Tunnel)
- [ ] DNS updated to point `tools.tablerocktx.com` to the server
- [ ] Systemd service enabled for auto-start on reboot
- [ ] Backup script and cron job configured
- [ ] Health check monitoring in place
- [ ] SSH hardened (key-only, no root login)
- [ ] Team members can connect via VPN and access the application
