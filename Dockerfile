# Table Rock Tools - Unified Production Dockerfile
# Builds React frontend and serves via FastAPI backend

# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Firebase config (public client-side values, not secrets)
ARG VITE_FIREBASE_API_KEY=AIzaSyDGTk6hpc4dk2MPGCBoky_kegUrg7dUuYk
ARG VITE_FIREBASE_AUTH_DOMAIN=tablerockenergy.firebaseapp.com
ARG VITE_FIREBASE_PROJECT_ID=tablerockenergy
ARG VITE_FIREBASE_STORAGE_BUCKET=tablerockenergy.firebasestorage.app
ARG VITE_FIREBASE_MESSAGING_SENDER_ID=781074525174
ARG VITE_FIREBASE_APP_ID=1:781074525174:web:f00b83c5401fe4b00d35d7
ARG VITE_FIREBASE_MEASUREMENT_ID=G-YZYXTHXBV9

# Copy package files for dependency caching
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy frontend source
COPY frontend/ ./

# Build production bundle (Vite picks up ARGs as env vars)
RUN VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID \
    VITE_FIREBASE_MEASUREMENT_ID=$VITE_FIREBASE_MEASUREMENT_ID \
    npm run build

# Stage 2: Production backend with built frontend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# - poppler-utils for pdf2image
# - tesseract-ocr for pytesseract
# - curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first for caching
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/app/ ./app/

# Copy data directory (allowed_users.json, etc.)
COPY backend/data/ ./data/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./static

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080
ENV ENVIRONMENT=production

# Expose port (Cloud Run uses 8080)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
