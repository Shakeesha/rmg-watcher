"""TransitFetcher protocol, live and mock clients, and client factory."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, Self
from urllib.parse import quote

import httpx

from transit_pipeline import __version__
from transit_pipeline.config import PROJECT_ROOT, Settings
from transit_pipeline.domain.exceptions import ApiError
from transit_pipeline.ingestion.retries import RetryPolicy, request_with_retries

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
DEFAULT_TIMEOUT_SECONDS = 10.0
API_KEY_HEADER = "X-Api-Key"

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


class LiveTransitClient:
    """HTTP client for the live transit API with strict timeouts and retries."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers=self._default_headers(api_key),
        )

    @staticmethod
    def _default_headers(api_key: str | None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": f"transit-telemetry/{__version__}",
        }
        if api_key:
            headers[API_KEY_HEADER] = api_key
        return headers

    def fetch_stops(self) -> RawPayload:
        return self._get_json("/stops", collection="stops")

    def fetch_departures(self, stop_id: str) -> RawPayload:
        path = f"/departures/{quote(stop_id, safe='')}"
        return self._get_json(path, collection="departures")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get_json(self, path: str, *, collection: str) -> RawPayload:
        response = request_with_retries(
            self._client,
            f"{self.base_url}{path}",
            policy=self.retry_policy,
            sleep=self._sleep,
        )
        try:
            document: object = response.json()
        except ValueError as exc:
            raise ApiError(f"Invalid JSON returned by {path}") from exc

        if isinstance(document, dict):
            document = document.get(collection) or []
        if not isinstance(document, list):
            raise ApiError(f"Unexpected payload shape returned by {path}")
        return [record for record in document if isinstance(record, dict)]


def create_fetcher(settings: Settings) -> TransitFetcher:
    """Build the fetcher selected by the current settings."""
    if settings.mock_mode:
        return MockTransitClient()
    if settings.transit_api_key is None:
        raise ApiError("TRANSIT_API_KEY is required in live mode")
    return LiveTransitClient(
        base_url=settings.transit_api_base_url,
        api_key=settings.transit_api_key.get_secret_value(),
    )
