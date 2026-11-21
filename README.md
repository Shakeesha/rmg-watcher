# RMG Watcher — Transit Delay Telemetry Device

Raspberry Pi 5 kiosk that ingests RMV/HEAG/DB transit data, stores it in SQLite,
and serves a small-screen Svelte UI from a single FastAPI process.

- **Backend:** Python 3.12, FastAPI, SQLite (WAL), httpx, Pydantic v2
- **Frontend:** Svelte 5 + TypeScript + Vite, compiled to static assets
- **Deployment:** systemd units for the Pi 5, touch-only kiosk, optional Compose image
- **Version:** 0.10.2

## Status

The pipeline, API, kiosk UI, CI workflow, and Raspberry Pi deployment assets are
implemented. See [CHANGELOG.md](CHANGELOG.md) for the release history and
[docs/architecture.md](docs/architecture.md) for the system design.

## Quickstart (development)

```bash
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"

cp .env.example .env                 # Windows: copy .env.example .env
# For a credential-free demo set PIPELINE_MOCK_MODE=true in .env.
```

Build the frontend once before starting the API:

```bash
cd frontend
npm ci
npm run build
cd ..
```

Run a pipeline batch and serve the UI:

```bash
python -m transit_pipeline run
python -m transit_pipeline serve
```

Open <http://127.0.0.1:8000/>. The mock data contains departures for
`luisenplatz` and `hbf`, including duplicates, malformed rows, and delays.

## CLI

| Command | Purpose |
| --- | --- |
| `python -m transit_pipeline ingest` | Fetch and snapshot raw payloads. |
| `python -m transit_pipeline transform` | Validate, deduplicate, and enrich without loading. |
| `python -m transit_pipeline run` | Full ingest, transform, load, and quality run. |
| `python -m transit_pipeline quality-check` | Re-run quality gates on the latest run. |
| `python -m transit_pipeline serve` | Serve the API and built frontend with Uvicorn. |

## API

| Endpoint | Description |
| --- | --- |
| `GET /api/health` | Database, pipeline, mock-mode, and version status. |
| `GET /api/stops` | Configured stops sorted by name. |
| `GET /api/departures/{stop_id}` | Departures for a stop with delay information. |
| `GET /api/metrics` | Punctuality, percentiles, top delayed routes, transfer risks. |

Interactive OpenAPI docs are available at `/docs`.

## Tests and static checks

```bash
python -m pytest
ruff check .
mypy

cd frontend
npm run check
npm run build
```

Tests force mock mode through `PYTEST_CURRENT_TEST` and block outbound sockets,
so the suite never contacts a live API. CI runs the same commands on Python 3.12
and Node 22.

## Raspberry Pi 5 deployment

Assumptions: Raspberry Pi 5 (4 GB) booted from the 256 GB NVMe SSD kit,
Raspberry Pi OS Bookworm 64-bit with a graphical session that auto-logs in as
`transit`, the Waveshare UPS HAT (E) on the pogo-pin connector, and the 5"
portrait touch display on DSI. The project is installed at `/opt/transit-kiosk`.

Boot from the SSD with `sudo raspi-config` (6 Advanced Options → A6 Boot Order →
NVMe) or by setting `BOOT_ORDER=0xf2` with `sudo rpi-eeprom-config --edit`, then
reboot and confirm the root device is `/dev/nvme0n1p2`.

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin transit
sudo usermod -aG video,render,audio transit
sudo mkdir -p /opt/transit-kiosk
sudo chown transit:transit /opt/transit-kiosk
sudo -u transit git clone <repository-url> /opt/transit-kiosk
cd /opt/transit-kiosk

sudo -u transit python3 -m venv .venv
sudo -u transit .venv/bin/pip install -e .
sudo -u transit cp .env.example .env
sudo chmod 600 .env
sudo -u transit mkdir -p data/raw data/quarantine
```

Set `PIPELINE_MOCK_MODE=false`, `TRANSIT_API_BASE_URL`, and `TRANSIT_API_KEY` in
`.env` for live data. Build the frontend either on the Pi or on a development
machine and copy `frontend/dist`:

```bash
sudo -u transit sh -c 'cd frontend && npm ci && npm run build'
```

Install and enable the services:

```bash
sudo install -m 0644 deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now transit-api.service transit-pipeline.timer transit-kiosk.service
```

`start-kiosk.sh` waits for the API and either a Wayland socket or an X display,
then launches Chromium fullscreen and restarts it if it exits. It derives
`XDG_RUNTIME_DIR` from the service user, so no hard-coded UID is needed.

### Container alternative

The Compose stack runs the API and a looping pipeline worker. The kiosk browser
still runs on the host so it can use the DSI touch display; the UPS HAT remains
independent of the containers.

```bash
cp .env.example .env          # configure credentials first
docker compose -f deploy/docker-compose.rpi5.yml up -d --build
```

## Layout

```text
src/transit_pipeline/   Python package (api, domain, ingestion, transform, storage, quality)
frontend/               Svelte + Vite kiosk UI
tests/                  pytest suite and fixtures
sql/                    Schema DDL and analytical queries
deploy/                 systemd units, kiosk scripts, Dockerfile, Compose file
.github/workflows/      CI workflow
docs/                   Architecture, schema, and hardware UI notes
data/                   Runtime storage (gitignored)
```

## Documentation

- [Architecture and memory budget](docs/architecture.md)
- [Star schema and metrics](docs/schema.md)
- [Kiosk layout and touch navigation](docs/hardware_ui.md)
