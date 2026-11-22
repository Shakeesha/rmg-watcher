# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY sql ./sql
COPY tests/fixtures ./tests/fixtures
RUN pip install --no-cache-dir -e .
COPY --from=frontend /frontend/dist ./frontend/dist
RUN useradd --create-home --uid 10001 transit \
    && mkdir -p /app/data \
    && chown -R transit:transit /app/data
USER transit
EXPOSE 8000
CMD ["rmg-watcher", "serve"]
