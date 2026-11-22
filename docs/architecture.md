# Architecture

The device is a single-process web service plus a periodic pipeline that share
one SQLite database. The Svelte kiosk is compiled to static files at build time
and served by FastAPI, so the Raspberry Pi never runs Node.js.

## Data flow

```text
RMV / HEAG / DB API  (or pytest fixtures in mock mode)
        |
        v
ingestion/fetcher.py -> retries.py -> raw_store.py
        |                              |
        |                              +-> data/raw/YYYY-MM-DD/<batch>.json
        v
transform/validator.py -> deduplicator.py -> enricher.py -> metrics.py
        |                       |
        |                       +-> quarantine records (with reasons/hashes)
        v
storage/repository.py (idempotent ON CONFLICT DO UPDATE)
        |
        +-> sql/schema.sql (SQLite WAL): dim_stops, dim_routes,
        |                               fact_stop_events, quarantine,
        |                               pipeline_runs
        v
quality/checks.py -> pipeline_runs.status
        |
        v
api/app.py  -- /api/health, /api/stops, /api/departures/{stop_id}, /api/metrics
        |
        v
frontend/dist (Svelte 5 kiosk) -- polls every 15 seconds
```

`rmg-watcher-pipeline.timer` starts one ingest -> transform -> load -> quality run
every 60 seconds. `rmg-watcher-api.service` keeps the read API and frontend online.
`rmg-watcher-kiosk.service` opens the built UI fullscreen on the attached touch
display and restarts the browser if it exits. There is no GPIO navigation
service: the display uses the GPIO header for power and the UPS HAT (E) powers
the Pi through pogo pins.

## Attached hardware

- **Raspberry Pi 5 (4 GB)** booted from the **256 GB NVMe SSD kit** (M.2 HAT+).
  The OS, project, SQLite database, raw snapshots, and quarantine files all
  live on the SSD, which avoids SD-card wear from the per-minute pipeline.
- **Waveshare UPS HAT (E)** connected via pogo pins; it provides 5 V / 6 A
  backup power and reports battery state over I²C. It does not consume GPIO
  pins for navigation.
- **Raspberry Pi Touch Display 2, 5" portrait** (720×1280) connected by DSI,
  with a five-finger capacitive touch panel. Navigation is entirely by touch.

## Memory budget (4 GB Raspberry Pi 5)

| Component | Budget |
| --- | --- |
| Raspberry Pi OS and Wayland compositor | ~600 MB |
| Chromium kiosk browser | ~900 MB |
| FastAPI / Uvicorn and SQLite | ~250 MB |
| Periodic pipeline process | ~150 MB |
| SQLite page cache and raw/quarantine I/O | ~200 MB |
| Reserve for spikes and journald | ~1.9 GB |

Systemd units cap the API at 768 MB, the pipeline at 512 MB, and the browser at
1.5 GB. The optional Compose deployment caps the API container at 768 MB and
the pipeline container at 512 MB, keeping total container memory at 1.28 GB.

## Live versus mock mode

- `PIPELINE_MOCK_MODE=false` (default) uses `TRANSIT_PROVIDER=transitous` and
  `TransitousClient`, which reads the MOTIS v6 API at
  `https://api.transitous.org/api/`. `TRANSIT_CONTACT` is required and is sent
  in the `User-Agent` as required by the Transitous usage policy.
- `TRANSIT_PROVIDER=generic` keeps the original `LiveTransitClient` for a
  custom REST API that already exposes `/stops` and `/departures/{stop_id}`.
- `PIPELINE_MOCK_MODE=true` uses `MockTransitClient` backed by
  `tests/fixtures/stops.json` and `sample_departures.json`. It is useful for
  demos and for verifying the UI without credentials.
- Under pytest, `Settings` forces mock mode whenever `PYTEST_CURRENT_TEST` is
  set. An autouse fixture also blocks outbound sockets, so a test can never
  reach the live API by accident.
- Raw payloads are written before transformation. Malformed records go to
  `quarantine` with a SHA-256 hash and a readable reason; they never reach the
  fact table.

### Transitous request budget

Transitous is a community service, so this client is deliberately quiet:

- The Darmstadt-Dieburg/Babenhausen stop catalog is downloaded at most once per
  24 hours and cached under `data/transitous/stops.json`.
- No stops are polled by default. `TRANSITOUS_WATCH_STOPS` is empty, so the
  pipeline does not generate a fixed baseline of departure requests.
- Departures are fetched on demand from the cached catalog and refreshed at most
  once every `TRANSITOUS_MIN_REFRESH_SECONDS` (600 seconds / 10 minutes).
- On open, the UI calls `/api/stops/suggested` and shows at most three nearby
  stops around `TRANSITOUS_HOME_LAT/LON`, or around the browser position after
  **Locate**. This is a local catalog lookup with no external request.
- Autocomplete uses a static catalog of German stops at
  `data/german-stops.json` (generated with `npm run build:stops`), so typing and
  selection work without a live lookup. Selecting a stop resolves its Transitous
  ID once through the cached geocoder.
- The **Connections** view uses the resource-heavy `/v6/plan` endpoint. Results
  are cached for 30 minutes per from/to/time/arriveBy bucket, and a daily
  counter caps fresh plan requests at `TRANSITOUS_PLAN_LIMIT_PER_DAY` (30).
- **Service alerts** are read from MOTIS stop-time alerts for the nearest stops
  (`TRANSITOUS_ALERT_STOPS`, default 3) and cached for 10 minutes.
- Route short names and transport-mode icons are used in the UI, so raw GTFS IDs
  are never shown to passengers.
- The nearby-stop map uses plain `<img>` tiles served by `/api/tiles/{z}/{x}/{y}.png`.
  The backend fetches each OpenStreetMap tile at most once every seven days and
  caches it on disk under `data/transitous/tiles`, so the Pi never runs a heavy
  mapping library and keeps external requests to a minimum. Markers and the user
  dot are positioned with pure Web Mercator math, so the map still works when
  tiles are unavailable.
- The UI links to `transitous.org/sources/` and OpenStreetMap attribution.

## Reliability

- Both live clients use strict timeouts; the generic client also retries HTTP
  429 and transient 5xx responses with exponential backoff and `Retry-After`.
- Fact rows are keyed by `(trip_id, stop_id)`, so repeated batches update in
  place instead of creating duplicates.
- Quality gates reconcile raw, valid, deduplicated, loaded, and quarantined
  counts and check nulls and foreign keys. Failures are recorded as
  `quality_failed` in `pipeline_runs`.
- The status banner reflects offline state, stale data, database health, the
  last pipeline run, mock mode, cancellations, and severe delays. A failed API
  poll serves the last cached timetable until Transitous returns.
- Connection warnings include service alerts that affect the journey routes.

## Deployment surfaces

- **Bare metal:** GitHub Actions packages the built frontend, static stop
  catalog, Python package, and systemd units into `rmg-watcher-rpi5.tar.gz`.
  Download it on the Pi and run `deploy/scripts/install-rpi5.sh`. No Node.js is
  needed on the device. See README.md.
- **Container:** `docker compose -f deploy/docker-compose.rpi5.yml up -d --build`
  builds a Python 3.12 image with the compiled frontend and runs the API plus a
  looping pipeline worker. The kiosk browser still runs on the host so it can
  use the DSI touch display and the UPS HAT's I²C monitoring.
