# RMG Watcher — Transit Delay Telemetry Device

Raspberry Pi 5 kiosk device that ingests RMV/HEAG/DB transit data, stores it in
SQLite, and serves a small-screen UI.

- **Backend:** Python 3.12, FastAPI, SQLite (WAL mode), httpx, Pydantic v2
- **Frontend:** Svelte 5 + TypeScript + Vite, built to static assets and served by FastAPI

## Status

v0.1.0 — project structure only. No pipeline or UI logic is implemented yet.

## Layout

```text
src/transit_pipeline/   Python package (api, domain, ingestion, transform, storage, quality)
frontend/               Svelte + Vite kiosk UI
tests/                  pytest suite and fixtures
sql/                    Schema DDL and analytical queries
deploy/                 systemd units, kiosk scripts, container config
docs/                   Architecture, schema, and hardware UI notes
data/                   Runtime storage (gitignored)
```

## Quickstart

TODO: document installation, mock mode, and the Pi deployment flow.
