# Multi-stage: build the React frontend with Node, serve it (and the API) from
# Python. The runtime image carries no Node and no build tooling.

# --- 1. frontend build -------------------------------------------------------
FROM node:24-alpine AS frontend

WORKDIR /build
# Dependencies first, so a source-only change reuses the install layer.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- 2. runtime --------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Unbuffered logs, no .pyc — the container filesystem is disposable.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# DATABASE_URL (a Postgres URL) is supplied by the deployment, never baked in:
# docker run -e DATABASE_URL=postgresql+psycopg://user:pass@host:5432/powertool

WORKDIR /app

# The server's runtime dependencies only, exactly pinned — the rest of
# requirements.txt is the test suite, which the runtime image has no use for.
COPY requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt

# An unprivileged user runs the app. The files below stay owned by root and
# world-readable, so the app can read but not change its own code; it writes
# nothing to the filesystem (the database is remote Postgres).
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY powertool/ ./powertool/
COPY backend/ ./backend/
COPY data/ ./data/
COPY --from=frontend /build/dist ./frontend/dist

USER app

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
