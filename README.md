# RMG Watcher — Transit Delay Telemetry Device

Raspberry Pi 5 kiosk that ingests RMV/HEAG/DB transit data, stores it in SQLite,
and serves a small-screen Svelte UI from a single FastAPI process.

- **Backend:** Python 3.12, FastAPI, SQLite (WAL), httpx, Pydantic v2
- **Frontend:** Svelte 5 + TypeScript + Vite, compiled to static assets
- **Deployment:** systemd units for the Pi 5, touch-only kiosk, optional Compose image
- **Version:** 0.13.1

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

## Live data with Transitous

The default live provider is [Transitous](https://transitous.org/api/), which
covers RMV, HEAG, and DB services in the Darmstadt-Dieburg area. To switch from
mock data:

1. Set these values in `.env`:

   ```ini
   PIPELINE_MOCK_MODE=false
   TRANSIT_PROVIDER=transitous
   TRANSIT_CONTACT=you@example.com        # or a project URL; required by Transitous
   ```

2. Optionally adjust the area and watchlist:

   ```ini
   TRANSITOUS_AREA_MIN=49.80,9.00
   TRANSITOUS_AREA_MAX=50.02,8.55
   TRANSITOUS_WATCH_STOPS=de-DELFI_de:06411:4734,de-amarillo-bw_de:06411:4736,de-DELFI_de:06432:8563
   TRANSITOUS_MIN_REFRESH_SECONDS=600
   TRANSITOUS_PLAN_LIMIT_PER_DAY=30
   TRANSITOUS_PLAN_CACHE_MINUTES=30
   TRANSITOUS_NEARBY_RADIUS_M=1000
   TRANSITOUS_NEARBY_LIMIT=8
   ```

3. Run `python -m transit_pipeline run` and serve the UI as above.

The default watchlist is Darmstadt Hbf, Darmstadt Luisenplatz, and Babenhausen
(Hess) Bahnhof. The full regional catalog is cached once per day under
`data/transitous/`, but only the watched stops are refreshed automatically.
Add more stop IDs to `TRANSITOUS_WATCH_STOPS` as needed — keep the list short to
respect the Transitous usage policy. At the default 10-minute refresh interval,
three stops generate roughly 432 API requests per day.

In the kiosk UI, press **Nearby** in the stop bar to list stops within 1 km of
the current stop and check their departures on demand. Those departures use the
same 10-minute cache, so repeated checks do not create extra requests.

The **Connections** view plans a trip between two stops. It caches results for
30 minutes and allows 30 fresh `/plan` requests per day by default; increase
`TRANSITOUS_PLAN_LIMIT_PER_DAY` only if your usage stays within the Transitous
policy.

The UI links to [Transitous sources](https://transitous.org/sources/) and
OpenStreetMap attribution. Consider
[donating to Transitous](https://transitous.org/donate/).

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

Set `PIPELINE_MOCK_MODE=false`, `TRANSIT_PROVIDER=transitous`, and a
`TRANSIT_CONTACT` value in `.env` for live data. Build the frontend either on
the Pi or on a development machine and copy `frontend/dist`:

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
- [Feature roadmap](docs/roadmap.md)
