# Table Rock Tools

Consolidated web application for Table Rock Energy's internal tools.

## Claude Permissions

- Git commits, pushes to `main`, and GitHub operations are allowed
- Deploying to Google Cloud Run (via `git push` triggering CI/CD) is allowed
- Running `npx tsc`, `python3` syntax checks, and build commands is allowed

## Project Structure

```
toolbox/
├── frontend/           # React + Vite + TypeScript + Tailwind
│   ├── src/
│   │   ├── components/ # Reusable UI components
│   │   ├── pages/      # Tool pages (Extract, Title, Proration, Revenue)
│   │   ├── layouts/    # MainLayout with sidebar navigation
│   │   └── utils/      # Helper functions
│   └── dist/           # Built production assets
├── backend/            # FastAPI Python backend
│   ├── app/
│   │   ├── api/        # Route handlers for each tool
│   │   ├── models/     # Pydantic models
│   │   ├── services/   # Business logic organized by tool
│   │   └── core/       # Configuration
│   └── data/           # RRC data storage
├── .github/workflows/  # CI/CD for Cloud Run deployment
├── Dockerfile          # Unified production container
├── docker-compose.yml  # Local development
└── Makefile            # Development commands
```

## Tools

| Tool | Route | Purpose |
|------|-------|---------|
| Extract | `/extract` | Extract party info from OCC Exhibit A PDFs |
| Title | `/title` | Consolidate owner info from title opinions |
| Proration | `/proration` | Mineral holders + RRC queries + NRA calculations |
| Revenue | `/revenue` | Extract revenue statements to M1 CSV format |

## Development

```bash
# Install dependencies
make install

# Run both frontend and backend in development
make dev

# Run with Docker
make docker-up
```

### URLs
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Deployment

Production is deployed to Google Cloud Run via GitHub Actions on push to `main`.

- **Project**: tablerockenergy
- **Service**: table-rock-tools
- **Region**: us-central1
- **URL**: https://tools.tablerocktx.com

### Manual Deploy
```bash
make deploy
```

## API Endpoints

All endpoints are prefixed with `/api`.

### Health
- `GET /api/health` - Service health check

### Extract Tool
- `POST /api/extract/upload` - Upload PDF, extract parties
- `POST /api/extract/export/csv` - Export to CSV
- `POST /api/extract/export/excel` - Export to Excel

### Title Tool
- `POST /api/title/upload` - Upload Excel/CSV
- `POST /api/title/preview` - Preview with filters
- `POST /api/title/export/csv` - Export to CSV
- `POST /api/title/export/excel` - Export to Excel

### Proration Tool
- `GET /api/proration/rrc/status` - RRC data status (includes DB counts)
- `POST /api/proration/rrc/download` - Download RRC data + sync to Firestore
- `POST /api/proration/rrc/sync` - Manual sync CSV data to Firestore
- `POST /api/proration/upload` - Process mineral holders CSV
- `POST /api/proration/export/excel` - Export to Excel
- `POST /api/proration/export/pdf` - Export to PDF

### Revenue Tool
- `POST /api/revenue/upload` - Upload revenue PDFs
- `POST /api/revenue/export/csv` - Export to M1 CSV

## Branding

- **Primary Navy**: #0e2431
- **Accent Teal**: #90c5ce
- **Tan**: #cab487
- **Font**: Oswald

## Key Dependencies

### Frontend
- React 19, React Router 7
- Vite 7, TypeScript 5
- Tailwind CSS 3
- Lucide React (icons)

### Backend
- FastAPI, Uvicorn
- Pandas, OpenPyXL (data processing)
- PyMuPDF, PDFPlumber (PDF extraction)
- ReportLab (PDF generation)
- BeautifulSoup4 (RRC scraping)
