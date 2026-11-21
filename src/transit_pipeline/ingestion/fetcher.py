"""TransitFetcher protocol, live and mock clients, and client factory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from transit_pipeline.config import PROJECT_ROOT, Settings
from transit_pipeline.domain.exceptions import ApiError

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

RawPayload = list[dict[str, Any]]


class TransitFetcher(Protocol):
    """Source of raw transit payloads."""

    def fetch_stops(self) -> RawPayload:
        """Return raw stop metadata."""

    def fetch_departures(self, stop_id: str) -> RawPayload:
        """Return raw departures for a single stop."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError(f"Could not read fixture {path}: {exc}") from exc


class MockTransitClient:
    """Deterministic client backed by JSON fixtures under ``tests/fixtures``."""

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR

    def fetch_stops(self) -> RawPayload:
        payload = _read_json(self.fixtures_dir / "stops.json")
        if not isinstance(payload, list):
            raise ApiError("stops.json must contain a JSON array")
        return [record for record in payload if isinstance(record, dict)]

    def fetch_departures(self, stop_id: str) -> RawPayload:
        payload = _read_json(self.fixtures_dir / "sample_departures.json")
        if not isinstance(payload, list):
            raise ApiError("sample_departures.json must contain a JSON array")
        return [
            record
            for record in payload
            if isinstance(record, dict) and record.get("stopId") == stop_id
        ]


def create_fetcher(settings: Settings) -> TransitFetcher:
    """Build the fetcher selected by the current settings."""
    if settings.mock_mode:
        return MockTransitClient()
    raise ApiError("Live transit client is not available yet")
