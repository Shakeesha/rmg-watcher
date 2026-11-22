"""TransitFetcher protocol, live and mock clients, and client factory."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, Self
from urllib.parse import quote

import httpx

from rmg_watcher import __version__
from rmg_watcher.config import PROJECT_ROOT, Settings
from rmg_watcher.constants import STOP_CATALOG_FILE
from rmg_watcher.domain.exceptions import ApiError
from rmg_watcher.ingestion.retries import RetryPolicy, request_with_retries
from rmg_watcher.ingestion.transitous import TransitousClient

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
DEFAULT_TIMEOUT_SECONDS = 10.0
API_KEY_HEADER = "X-Api-Key"
TIME_FIELDS = ("scheduledTime", "expectedTime")

RawPayload = list[dict[str, Any]]


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _freshen_departures(records: RawPayload) -> RawPayload:
    """Move fixture departure times into the near future.

    The JSON fixtures have fixed timestamps, which would make a long-running
    mock kiosk show departures from the past. The whole batch is shifted by the
    same amount so delay deltas stay realistic. Unparseable values are left
    alone so the fixture keeps exercising quarantine handling.
    """
    scheduled = [
        parsed for record in records if (parsed := _parse_time(record.get("scheduledTime")))
    ]
    if not scheduled:
        return records

    earliest = min(scheduled)
    if earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=UTC)
    zone = earliest.tzinfo
    target = datetime.now(zone).replace(second=0, microsecond=0) + timedelta(minutes=1)
    target += timedelta(minutes=(5 - target.minute % 5) % 5)
    offset = target - earliest

    result: RawPayload = []
    for record in records:
        item = dict(record)
        for field in TIME_FIELDS:
            parsed = _parse_time(item.get(field))
            if parsed is None:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            item[field] = (parsed + offset).isoformat()
        result.append(item)
    return result


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
    """Client backed by realistic JSON fixtures under ``tests/fixtures``.

    Records mirror the normalized shape produced by ``TransitousClient`` and are
    shifted to the upcoming hour so a mock kiosk shows plausible departures.
    Two luisenplatz records are deliberately malformed to exercise quarantine.
    """

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR

    def fetch_stops(self) -> RawPayload:
        payload = _read_json(self.fixtures_dir / STOP_CATALOG_FILE)
        if not isinstance(payload, list):
            raise ApiError(f"{STOP_CATALOG_FILE} must contain a JSON array")
        return [record for record in payload if isinstance(record, dict)]

    def fetch_departures(self, stop_id: str) -> RawPayload:
        payload = _read_json(self.fixtures_dir / "sample_departures.json")
        if not isinstance(payload, list):
            raise ApiError("sample_departures.json must contain a JSON array")
        records = [
            record
            for record in payload
            if isinstance(record, dict) and record.get("stopId") == stop_id
        ]
        return _freshen_departures(records)


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
    if settings.transit_provider == "transitous":
        return TransitousClient(settings)
    if settings.transit_provider == "generic":
        if settings.transit_api_key is None:
            raise ApiError("TRANSIT_API_KEY is required in live mode")
        return LiveTransitClient(
            base_url=settings.transit_api_base_url,
            api_key=settings.transit_api_key.get_secret_value(),
        )
    raise ApiError(f"Unsupported transit provider: {settings.transit_provider}")
