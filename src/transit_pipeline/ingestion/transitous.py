"""Transitous MOTIS API client with a deliberately low request rate.

Transitous is a community service: see https://transitous.org/api/ for its
usage policy. This client therefore downloads the regional stop catalog at most
once per day and caches departures for each watched stop for a configurable
minimum interval (10 minutes by default).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import httpx

from transit_pipeline import __version__
from transit_pipeline.config import Settings
from transit_pipeline.domain.exceptions import ApiError

CATALOG_TTL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 10.0


def _records(value: object) -> list[dict[str, Any]]:
    """Return only dictionary items, ignoring malformed source entries."""
    if not isinstance(value, list):
        raise ApiError("Unexpected Transitous payload shape: expected a list")
    return [item for item in value if isinstance(item, dict)]


class TransitousClient:
    """Fetch stops and departures from the Transitous MOTIS v6 API."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        contact = (settings.transitous_contact or "").strip()
        if not contact:
            raise ApiError(
                "TRANSIT_CONTACT is required for Transitous requests; "
                "use an email address or project URL"
            )

        base_url = settings.transitous_base_url.rstrip("/")
        if not base_url.endswith("/api"):
            base_url = f"{base_url}/api"

        self._settings = settings
        self._now = now or (lambda: datetime.now(UTC))
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            headers={
                "Accept": "application/json",
                "User-Agent": f"rmg-watcher/{__version__} ({contact})",
            },
        )
        self._cache_dir = settings.transitous_cache_path
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client if this object owns it."""
        if self._owns_client:
            self._client.close()

    def fetch_stops(self) -> list[dict[str, Any]]:
        """Return the configured watch stops, enriched from the regional catalog."""
        catalog = self._fetch_catalog()
        by_id = {str(stop["stopId"]): stop for stop in catalog}
        result: list[dict[str, Any]] = []
        for stop_id in self._settings.transitous_watch_stops:
            stop = by_id.get(stop_id)
            if stop is None:
                stop = {
                    "stopId": stop_id,
                    "name": stop_id,
                    "latitude": None,
                    "longitude": None,
                }
            result.append(stop)
        return result

    def _fetch_catalog(self) -> list[dict[str, Any]]:
        """Download and cache the deduplicated stop catalog for the area."""
        cache_path = self._cache_dir / "stops.json"
        cached = self._read_cache(cache_path, CATALOG_TTL_SECONDS)
        if cached is not None:
            return _records(cached)

        payload = self._get(
            "/v6/map/stops",
            params={
                "min": self._settings.transitous_area_min,
                "max": self._settings.transitous_area_max,
            },
        )
        stops: dict[tuple[str, float, float], dict[str, Any]] = {}
        for item in _records(payload):
            stop_id = item.get("stopId")
            name = item.get("name")
            lat = item.get("lat")
            lon = item.get("lon")
            if not isinstance(stop_id, str) or not stop_id:
                continue
            if not isinstance(name, str) or not name:
                continue
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue

            stop = {
                "stopId": stop_id,
                "name": name,
                "latitude": float(lat),
                "longitude": float(lon),
            }
            key = (name, round(float(lat), 3), round(float(lon), 3))
            existing = stops.get(key)
            if existing is None or len(stop_id) < len(str(existing["stopId"])):
                stops[key] = stop

        result = sorted(stops.values(), key=lambda stop: str(stop["name"]))
        self._write_cache(cache_path, result)
        return result

    def fetch_departures(self, stop_id: str) -> list[dict[str, Any]]:
        """Return cached or freshly fetched departure records for one stop."""
        digest = hashlib.sha256(stop_id.encode("utf-8")).hexdigest()[:20]
        cache_path = self._cache_dir / "departures" / f"{digest}.json"
        cached = self._read_cache(
            cache_path,
            self._settings.transitous_min_refresh_seconds,
        )
        if cached is not None:
            return _records(cached)

        payload = self._get(
            "/v6/stoptimes",
            params={
                "stopId": stop_id,
                "n": self._settings.transitous_departure_limit,
                "realtimeMode": "REALTIME",
                "language": "de",
            },
        )
        if not isinstance(payload, dict):
            raise ApiError("Unexpected Transitous stoptimes payload")

        result = [
            record
            for stop_time in _records(payload.get("stopTimes"))
            if (record := self._map_stop_time(stop_time, stop_id)) is not None
        ]
        self._write_cache(cache_path, result)
        return result

    def _get(self, path: str, *, params: dict[str, str | int]) -> object:
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ApiError(f"Transitous request to {path} failed: {exc}") from exc
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(f"Invalid JSON returned by {path}") from exc

    def _map_stop_time(
        self,
        stop_time: dict[str, Any],
        stop_id: str,
    ) -> dict[str, Any] | None:
        place = stop_time.get("place")
        if not isinstance(place, dict):
            return None

        trip_id = stop_time.get("tripId")
        route_id = stop_time.get("routeId")
        if not isinstance(trip_id, str) or not trip_id:
            return None
        if not isinstance(route_id, str) or not route_id:
            return None

        scheduled = place.get("scheduledDeparture") or place.get("scheduledArrival")
        expected = place.get("departure") or place.get("arrival")
        if scheduled is None:
            scheduled = expected
        if not isinstance(scheduled, str) or not scheduled:
            return None

        real_time = bool(stop_time.get("realTime"))
        expected_value = None if not real_time or not isinstance(expected, str) else expected

        cancelled = bool(
            stop_time.get("cancelled")
            or stop_time.get("tripCancelled")
            or place.get("cancelled")
        )
        status = "cancelled" if cancelled else ("delayed" if real_time else "on_time")
        mode = stop_time.get("mode")
        short_name = stop_time.get("routeShortName") or stop_time.get("displayName")

        return {
            "tripId": trip_id,
            "routeId": route_id,
            "stopId": stop_id,
            "scheduledTime": scheduled,
            "expectedTime": expected_value,
            "status": status,
            "routeShortName": short_name if isinstance(short_name, str) else None,
            "routeMode": mode.lower() if isinstance(mode, str) else None,
        }

    def _read_cache(self, path: Path, ttl_seconds: int) -> object | None:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(document, dict):
            return None

        fetched_at = document.get("fetched_at")
        if not isinstance(fetched_at, str):
            return None
        try:
            fetched = datetime.fromisoformat(fetched_at)
        except ValueError:
            return None
        if (self._now() - fetched).total_seconds() > ttl_seconds:
            return None
        return document.get("payload")

    def _write_cache(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        document = {
            "fetched_at": self._now().isoformat(),
            "payload": payload,
        }
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
