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
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////data/powertool.db

WORKDIR /app

# The server's runtime dependencies only — the rest of requirements.txt is
# tests and the frozen Streamlit app, which would add ~200 MB of pandas and
# friends the API never imports.
# ponytail: versions duplicated from requirements.txt (see the marks there);
# fold into a requirements-server.txt if this list grows.
RUN pip install --no-cache-dir \
    "pyyaml>=6.0" \
    "reportlab>=4.0" \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.29" \
    "sqlalchemy>=2.0"

COPY powertool/ ./powertool/
COPY backend/ ./backend/
COPY data/ ./data/
COPY --from=frontend /build/dist ./frontend/dist

# The SQLite file lives on a volume so projects and designs survive the
# container. Mount it: docker run -v powertool-data:/data
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
