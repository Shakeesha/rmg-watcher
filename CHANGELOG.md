# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.21.2] - 2026-11-23

### Fixed

- The Raspberry Pi release archive and container image now include `docs/`, so
  the downloaded artifact is sufficient for both the bare-metal installer and a
  standalone `docker build`. CI checks for the documentation files explicitly.
- Synchronized `frontend/package-lock.json` with the current package version.

### Added

- `AGENTS.md` as the canonical, persistent process manual covering identity,
  hardware/runtime constraints, Transitous policy, the `.env` read prohibition,
  commit/versioning rules, and the verification gate.

## [0.21.1] - 2026-11-22

### Fixed

- Mock departures now carry the same normalized fields as live Transitous
  records, including wheelchair accessibility.
- Mock timestamps are shifted to a near-future slot on each read instead of
  staying frozen in the past. The two deliberate malformed fixtures remain for
  quarantine testing.

## [0.21.0] - 2026-11-22

### Added

- Pre-deployment CI covering backend tests on Python 3.11 and 3.12, ruff lint
  and format checks, mypy, frontend checks and build, Python and Node dependency
  audits, configuration validation, an archive installation smoke test, and a
  container build.
- A deployment gate that must pass before a release archive is attached to a tag.
- A test that `.env.example` documents every settings field.

## [0.20.3] - 2026-11-22

### Changed

- Grouped constants into labelled sections in both Python and TypeScript
  constant files.

## [0.20.2] - 2026-11-22

### Changed

- App descriptions, CLI help, API metadata, and module comments now expand RMG
  as Rhein-Main-Gebiet. The README also reflects the Python 3.11+ baseline.

## [0.20.1] - 2026-11-22

### Fixed

- Target stock Raspberry Pi OS Bookworm: Python 3.11 is now supported, CI checks
  both 3.11 and 3.12, and the distro `chromium` package is used.
- Installer adds missing packages, enables user lingering, and no longer risks
  corrupting files when the archive is extracted into its own install directory.
- Release archive now includes the frontend manifests and mock fixtures so the
  Compose build works directly from the downloaded artifact.

## [0.20.0] - 2026-11-22

### Added

- Street-map style nearby view backed by a disk-cached OpenStreetMap tile proxy.
  Mode-coloured markers, a user location dot, and a nearby-stop bottom sheet
  replace the old schematic map.
- Cached raster tiles need no mapping library, keeping the Pi 5 footprint small.

## [0.19.1] - 2026-11-22

### Changed

- Stop searches and nearby lists consolidate obvious name variants such as
  `Darmstadt Hbf`, `Darmstadt Hauptbahnhof`, and `Darmstadt Central Station`.

## [0.19.0] - 2026-11-22

### Added

- GitHub Actions packaging job that builds a Raspberry Pi 5 release archive
  with the frontend, static stop catalog, Python package, and systemd units.
- `deploy/scripts/install-rpi5.sh` for one-command installation on the Pi.
- Release job that attaches the Raspberry Pi archive to version tags.

## [0.18.3] - 2026-11-22

### Fixed

- Walking transfers now show an explicit right-facing direction indicator.

## [0.18.2] - 2026-11-22

### Changed

- Cache and index the regional stop catalog, reuse one event query for metrics,
  and consolidate retry logic and repeated literals.
- Remove unused domain types and duplicated stop-name normalization.

## [0.18.1] - 2026-11-22

### Changed

- Patch version bump for the environment documentation and cleanup refactors
  in this series.

## [0.18.0] - 2026-11-22

### Added

- Connection results open as a compact list of route chips; selecting one shows
  the detailed leg view with intermediate stops and platforms.
- Every `.env` and `.env.example` variable now documents its purpose, allowed
  values, and default.
- Magic numbers across the backend and frontend are now named constants.
- Duplicated formatting helpers are consolidated in `frontend/src/lib/format.ts`.

## [0.17.3] - 2026-11-22

### Fixed

- Walking legs are included in transfer windows, so short walks no longer
  create false tight-transfer warnings.
- Favourite labels and swapped fields use stop names instead of Transitous IDs.

## [0.17.2] - 2026-11-22

### Fixed

- Space and arrow keys work normally inside text inputs, so station names with
  spaces can be typed.

## [0.17.1] - 2026-11-22

### Fixed

- Autocomplete suggestions close completely after a selection.
- Connection searches send a timezone-aware timestamp, fixing `400/502`
  errors from the date/time picker.

## [0.17.0] - 2026-11-22

### Added

- Connection warnings now consider service alerts affecting the journey routes.
- Departures expose wheelchair accessibility with an accessible-only filter.
- Departure cache now serves stale timetable data when Transitous is offline.
- Cancellations and severe delays are promoted into the status banner.

### Removed

- `docs/roadmap.md`; all its remaining features are now implemented and
  documented in the architecture and hardware UI notes.

## [0.16.2] - 2026-11-22

### Fixed

- Connection autocomplete closes after a selection and blocks search until the
  Transitous ID has resolved.
- Free multi-word typing in both From and To fields no longer reopens the
  suggestion list after selection.
- Suggested stops are limited to three and fetched only on initial load or
  after using **Locate**.
- Browser tab and top-left badge now show `RMG-Watcher`; the separate label next
  to the badge was removed.

## [0.16.1] - 2026-11-22

### Fixed

- Local stop search now matches multi-word queries with spaces and punctuation,
  including place suffixes such as `(Hessen)`.
- Renamed the application to `RMG-Watcher` in the UI and `rmg-watcher` in
  packages, the `rmg-watcher` CLI command, and deployment units.
- Moved the Python package from `src/transit_pipeline` to `src/rmg_watcher` and
  removed the old module name entirely.

## [0.16.0] - 2026-11-22

### Added

- Static German stop catalog at `data/german-stops.json` for offline autocomplete
  and selection.
- One-time `npm run build:stops` generator using DB HAFAS open data.
- Place resolution that maps a static stop to its Transitous ID once and caches
  the result.

### Fixed

- Geocoder type filter no longer uses the invalid `POI` value.

## [0.15.1] - 2026-11-22

### Fixed

- Retry transient Transitous HTTP 429/5xx responses once.
- Show a friendly message instead of a raw API 502 during connection lookup.

## [0.15.0] - 2026-11-22

### Added

- Nationwide stop autocomplete backed by a cached Transitous geocoder.
- Typed From/To fields for connections that accept any stop in Germany.

## [0.14.0] - 2026-11-22

### Added

- Tight-transfer warnings on connection results when a change is five minutes
  or less.

### Removed

- The standalone Transfers view; transfer risk is now shown in context on
  selected connections.

## [0.13.1] - 2026-11-22

### Fixed

- Service alerts now degrade to an empty list instead of showing a raw API 502.
- Live and nearby stop lists are limited to three suggested stops.
- Transfer risks show readable stop names, and a failing optional request no
  longer marks the whole service as offline.

## [0.13.0] - 2026-11-22

### Added

- Search field and transport-mode icons in the nearby stop list.
- Lightweight local map of nearby stops, drawn without external tiles.
- Departures/Arrivals toggle backed by MOTIS `arriveBy`.
- From/To swap, quick time chips, and earlier/later controls for connections.
- Route-coloured journey bars, platforms, operator info, and expandable intermediate stops.

## [0.12.0] - 2026-11-22

### Added

- Nearby stops are suggested on open from the cached catalog instead of polling
  a fixed watchlist; the **Locate** button uses browser geolocation.
- Transport-mode icons on departure rows.
- Favourite connections stored in the browser.
- Date/time picker with departure or arrival selection for connections.
- Service alerts view using cached MOTIS alerts for nearby stops.

### Changed

- Departure refresh remains at 10 minutes; connection searches stay capped at
  30 fresh requests per day.

## [0.11.0] - 2026-11-22

### Added

- `TransitousClient` for live RMV/HEAG/DB data via the Transitous MOTIS v6 API.
- Required `TRANSIT_CONTACT` in the User-Agent, per the Transitous usage policy.
- Daily cached stop catalog and per-stop departure cache with a 10-minute
  minimum refresh interval to keep request volume low.
- Configurable Darmstadt-Dieburg/Babenhausen bounding box and watched-stop list.
- Optional **Nearby** stop checks in the kiosk UI using the cached catalog and
  on-demand cached departures.
- **Connections** view with cached `/v6/plan` searches and a daily request cap.
- Readable route short names in delay and transfer views instead of raw IDs.
- Transitous and OpenStreetMap attribution in the kiosk UI and README.
- Feature roadmap based on DB Navigator and HEAG mobilo.
- Tests for Transitous mapping, caching, contact enforcement, nearby stops,
  connections, and the live departures endpoint.

### Fixed

- Duplicate stop names in the stop bar and nearby list.

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
- `rmg-watcher` entry point.
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
- Stop and departure fixtures covering valid, duplicate, canceled, and
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

- Environment-backed `Settings` model in `rmg_watcher.config` covering
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
- Python package skeleton under `src/rmg_watcher`.
- Svelte 5 + Vite + TypeScript frontend scaffold under `frontend/`.
- SQL, documentation, deployment, and CI placeholders.
- Tooling configuration: `pyproject.toml`, `.gitignore`, `.env.example`.
