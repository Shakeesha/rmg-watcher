# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.11.0] - 2026-11-22

### Added

- `TransitousClient` for live RMV/HEAG/DB data via the Transitous MOTIS v6 API.
- Required `TRANSIT_CONTACT` in the User-Agent, per the Transitous usage policy.
- Daily cached stop catalog and per-stop departure cache with a 7-minute
  minimum refresh interval to keep request volume low.
- Configurable Darmstadt-Dieburg/Babenhausen bounding box and watched-stop list.
- Optional **Nearby** stop checks in the kiosk UI using the cached catalog and
  on-demand cached departures.
- Transitous and OpenStreetMap attribution in the kiosk UI and README.
- Tests for Transitous mapping, caching, contact enforcement, nearby stops, and
  the live departures endpoint.

## [0.10.2] - 2026-11-22

### Fixed

- Docker image now includes `tests/fixtures`, so `PIPELINE_MOCK_MODE=true`
  works inside the Compose containers instead of failing to read `stops.json`.

## [0.10.1] - 2026-11-21

### Removed

- `gpio_to_keys.py` and `transit-gpio-nav.service`. The attached 5" portrait
  touch display takes power from the GPIO header and the UPS HAT (E) uses pogo
  pins, so there are no GPIO pins available for navigation buttons.

### Changed

- Deployment and hardware documentation now target the 256 GB NVMe SSD, the
  Waveshare UPS HAT (E), and the 720×1280 DSI capacitive touch display.
- The kiosk is documented as touch-only; keyboard handling remains for
  development and debugging.

## [0.10.0] - 2026-11-21

### Added

- Systemd units for the API, one-shot pipeline, pipeline timer, fullscreen
  kiosk browser, and optional GPIO navigation bridge.
- Kiosk launcher with API/display readiness checks and automatic crash
  recovery.
- gpiozero-to-evdev bridge for five physical navigation buttons.
- Dockerfile and Compose stack for the API and periodic pipeline worker with
  strict 4 GB RAM limits.
- GitHub Actions CI running pytest, ruff, mypy, svelte-check, and the Vite build.
- Architecture, hardware UI, and deployment documentation.

## [0.9.0] - 2026-11-21

### Added

- Svelte 5 kiosk UI with Live, Delays, and Transfers views.
- Typed API client and shared TypeScript interfaces matching the FastAPI
  response schemas.
- Unified touch, keyboard, and hardware-button navigation controller with
  focus management and view cycling.
- Persisted stop selection, 15-second polling, online/offline handling, and
  automatic retry after failures.
- Status banner covering connection state, stale data, database and pipeline
  health, and mock mode.
- High-contrast responsive styling for 800x480 and 1024x600 displays.
- Transfer-risk list with at-risk connection highlighting.
- Hardware UI layout and navigation documentation.

## [0.8.0] - 2026-11-21

### Added

- FastAPI application factory with lifespan-managed SQLite initialization.
- Read endpoints: `/api/health`, `/api/stops`, `/api/departures/{stop_id}`, and
  `/api/metrics`.
- Metrics response with punctuality, median/p95 delays, top delayed routes, and
  transfer risks.
- Static frontend serving with `/assets` mounting and an SPA fallback.
- `serve` CLI command backed by Uvicorn.
- API tests covering endpoints, errors, and static serving.

## [0.7.0] - 2026-11-21

### Added

- `TransitRepository` with idempotent dimension and fact upserts, quarantine
  logging, and UI read queries.
- Data quality gates reconciling raw, valid, loaded, deduplicated, and
  quarantined counts plus null and foreign-key checks.
- Pipeline orchestration for the ingest, transform, load, and quality phases.
- CLI commands: `ingest`, `transform`, `run`, and `quality-check`.
- `python -m transit_pipeline` entry point.
- Analytical SQL queries for punctuality, top delays, and pipeline runs.
- Storage, quality, CLI, and end-to-end pipeline tests.

## [0.6.0] - 2026-11-21

### Added

- Pydantic departure validation with camelCase aliases, timezone
  normalization, status normalization, and plausibility bounds.
- Quarantine records with stable SHA-256 hashes and human-readable reasons.
- O(1) deduplication keyed on `(trip_id, stop_id)`.
- Delay enrichment with on-time, minor, major, severe, and cancelled
  categories.
- Metrics for punctuality, median and p95 delays, top-k delayed routes, and
  transfer-connection risk.
- Helpers that derive domain stops and routes from raw payloads.
- Transformation tests covering duplicates, malformed records, boundaries, and
  transfer risk.

## [0.5.0] - 2026-11-21

### Added

- `LiveTransitClient` with API-key headers, strict timeouts, and support for
  list and wrapped collection payloads.
- Retry policy with exponential backoff, `Retry-After` handling, and retries
  for transient HTTP status codes.
- `RawStore` for atomic, date-partitioned raw payload snapshots with batch
  metadata.
- Live client, retry, and raw storage tests.

## [0.4.0] - 2026-11-21

### Added

- `TransitFetcher` protocol and a deterministic `MockTransitClient` backed by
  JSON fixtures.
- Fetcher factory that selects the mock client in mock mode.
- Shared pytest fixtures for isolated settings and mock fetching.
- Autouse outbound network guard that blocks non-local socket connections.
- Stop and departure fixtures covering valid, duplicate, cancelled, and
  malformed records.

## [0.3.0] - 2026-11-21

### Added

- Domain models and enums: `Stop`, `Route`, `TripUpdate`, `DelayEvent`,
  `TripStatus`, and `DelayCategory`.
- SQLite star schema with `dim_stops`, `dim_routes`, `fact_stop_events`,
  `quarantine`, and `pipeline_runs`.
- `Database` connection manager with WAL mode, foreign keys, busy timeout, and
  idempotent schema initialization.
- Schema and WAL-mode tests.

## [0.2.0] - 2026-11-21

### Added

- Environment-backed `Settings` model in `transit_pipeline.config` covering
  pipeline paths, live API credentials, and API server options.
- Automatic mock mode while `PYTEST_CURRENT_TEST` is set, plus an explicit
  `PIPELINE_MOCK_MODE` switch for normal execution.
- Blank `TRANSIT_API_KEY` values are treated as missing, and API keys are
  masked in logs and representations.
- Tests for mock-mode switching, project defaults, environment overrides, and
  secret handling.

## [0.1.0] - 2026-11-21

### Added

- Initial project structure for the transit telemetry device.
- Python package skeleton under `src/transit_pipeline`.
- Svelte 5 + Vite + TypeScript frontend scaffold under `frontend/`.
- SQL, documentation, deployment, and CI placeholders.
- Tooling configuration: `pyproject.toml`, `.gitignore`, `.env.example`.
