# Table Rock Tools

Consolidated web application for Table Rock Energy's internal tools.

**Production URL**: https://tools.tablerocktx.com

## Tools

| Tool | Purpose |
|------|---------|
| **Extract** | Extract party/stakeholder info from OCC Exhibit A PDFs |
| **Title** | Consolidate owner/contact info from title opinions |
| **Proration** | Mineral holders + RRC queries + NRA calculations |
| **Revenue** | Extract revenue statements (EnergyLink/Energy Transfer) |

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

Automatic deployment via GitHub Actions on push to `main` branch.

- **GCP Project**: tablerockenergy
- **Service**: table-rock-tools
- **Region**: us-central1

### Manual Deploy

```bash
make deploy
```

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
