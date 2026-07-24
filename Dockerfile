# syntax=docker/dockerfile:1

# ── Backend build stage ──────────────────────────
FROM python:3.12-slim AS backend-build
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Frontend build stage ─────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install
COPY frontend/ .
RUN npm run build

# ── Production stage ─────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1001 appuser

# Copy Python deps from build stage
COPY --from=backend-build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-build /usr/local/bin /usr/local/bin

# Copy backend source
COPY backend/ .
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Copy frontend build
COPY --from=frontend-build /app/dist /app/frontend/dist

ENV FRONTEND_DIST=/app/frontend/dist
ENV PYTHONUNBUFFERED=1
EXPOSE 8001

USER appuser

# Migration first, then single-worker uvicorn (SQLite-safe)
CMD ["sh", "-c", "python -m alembic -c /app/alembic.ini upgrade head || echo 'WARNING: Migration failed, continuing...'; exec uvicorn app.main:app --host 0.0.0.0 --port 8001"]
