# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
