.PHONY: help install dev build test clean docker-build docker-up docker-down deploy

# Default target
help:
	@echo "Table Rock Tools - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install all dependencies (frontend + backend)"
	@echo "  make install-frontend  Install frontend dependencies only"
	@echo "  make install-backend   Install backend dependencies only"
	@echo ""
	@echo "Development:"
	@echo "  make dev            Run both frontend and backend in development mode"
	@echo "  make dev-frontend   Run frontend development server only"
	@echo "  make dev-backend    Run backend development server only"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-backend   Run backend tests only"
	@echo "  make lint           Run linting"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker images"
	@echo "  make docker-up      Start Docker containers"
	@echo "  make docker-down    Stop Docker containers"
	@echo ""
	@echo "Production:"
	@echo "  make build          Build for production"
	@echo "  make deploy         Deploy to Cloud Run"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean          Remove build artifacts and caches"

# Installation
install: install-frontend install-backend

install-frontend:
	cd frontend && npm install

install-backend:
	cd backend && pip install -r requirements.txt

# Development
dev:
	@echo "Starting development servers..."
	@trap 'kill 0' INT; \
	(cd backend && uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

dev-frontend:
	cd frontend && npm run dev

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

# Testing
test: test-backend

test-backend:
	cd backend && pytest -v

lint:
	cd backend && ruff check app/
	cd frontend && npm run lint

# Docker
docker-build:
	docker build -t tablerock-tools:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Production build
build:
	cd frontend && npm run build
	@echo "Frontend built to frontend/dist/"

# Deploy to Cloud Run
deploy: build
	gcloud run deploy table-rock-tools \
		--source . \
		--project tablerockenergy \
		--region us-central1 \
		--allow-unauthenticated

# Clean up
clean:
	rm -rf frontend/dist
	rm -rf frontend/node_modules
	rm -rf backend/__pycache__
	rm -rf backend/app/__pycache__
	rm -rf backend/app/**/__pycache__
	rm -rf backend/.pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
