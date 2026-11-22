"""Transitous MOTIS API client with a deliberately low request rate.

Transitous is a community service: see https://transitous.org/api/ for its
usage policy. This client therefore downloads the regional stop catalog at most
once per day and caches departures for each watched stop for a configurable
minimum interval (10 minutes by default). Connection searches use a separate
daily request cap.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

import httpx

from rmg_watcher import __version__
from rmg_watcher.config import Settings
from rmg_watcher.domain.exceptions import ApiError

CATALOG_TTL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 10.0
RETRY_STATUSES = {429, 500, 502, 503, 504}


def _records(value: object) -> list[dict[str, Any]]:
    """Return only dictionary items, ignoring malformed source entries."""
    if not isinstance(value, list):
        raise ApiError("Unexpected Transitous payload shape: expected a list")
    return [item for item in value if isinstance(item, dict)]


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Return the great-circle distance between two coordinates in metres."""
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    h = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return int(2 * radius * math.asin(math.sqrt(h)))


def _prefer_stop(candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    """Prefer parent stop IDs over platform-level IDs."""
    candidate_id = str(candidate["stopId"])
    existing_id = str(existing["stopId"])
    if len(candidate_id) != len(existing_id):
        return len(candidate_id) < len(existing_id)
    return candidate_id.count(":") < existing_id.count(":")


def normalize_stop_name(name: str) -> str:
    """Normalise a stop name so platform variants collapse to one entry."""
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def load_cached_stops(cache_path: Path) -> list[dict[str, Any]]:
    """Read the cached stop catalog without making an API request."""
    try:
        document = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(document, dict):
        return []
    return _records(document.get("payload"))


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
            key = (
                normalize_stop_name(name),
                round(float(lat), 2),
                round(float(lon), 2),
            )
            existing = stops.get(key)
            if existing is None or _prefer_stop(stop, existing):
                stops[key] = stop

        result = sorted(stops.values(), key=lambda stop: str(stop["name"]))
        self._write_cache(cache_path, result)
        return result

    def fetch_departures(self, stop_id: str, *, arrive_by: bool = False) -> list[dict[str, Any]]:
        """Return cached or freshly fetched departure/arrival records for one stop."""
        digest = hashlib.sha256(
            f"{stop_id}|{int(arrive_by)}".encode()
        ).hexdigest()[:20]
        cache_path = self._cache_dir / "departures" / f"{digest}.json"
        cached = self._read_cache(
            cache_path,
            self._settings.transitous_min_refresh_seconds,
        )
        if cached is not None:
            return _records(cached)

        try:
            payload = self._get(
                "/v6/stoptimes",
                params={
                    "stopId": stop_id,
                    "n": self._settings.transitous_departure_limit,
                    "arriveBy": arrive_by,
                    "realtimeMode": "REALTIME",
                    "language": "de",
                },
            )
        except ApiError:
            stale = self._read_cache_any(cache_path)
            if stale is not None:
                return _records(stale)
            raise
        if not isinstance(payload, dict):
            raise ApiError("Unexpected Transitous stoptimes payload")

        result = [
            record
            for stop_time in _records(payload.get("stopTimes"))
            if (record := self._map_stop_time(stop_time, stop_id, arrive_by)) is not None
        ]
        self._write_cache(cache_path, result)
        return result

    def suggested_stops(
        self,
        latitude: float,
        longitude: float,
        radius_m: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Return nearby stops from the cached catalog without an API call."""
        candidates: list[tuple[int, dict[str, Any]]] = []
        seen: set[str] = set()
        for item in self._fetch_catalog():
            stop_id, name = item.get("stopId"), item.get("name")
            lat, lon = item.get("latitude"), item.get("longitude")
            if not isinstance(stop_id, str) or not isinstance(name, str):
                continue
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            distance = distance_meters(latitude, longitude, float(lat), float(lon))
            if distance > radius_m:
                continue
            key = normalize_stop_name(name)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                (
                    distance,
                    {
                        "stopId": stop_id,
                        "name": name,
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "distance_m": distance,
                    },
                )
            )
        candidates.sort(key=lambda entry: entry[0])
        return [stop for _, stop in candidates[:limit]]

    def fetch_alerts(self, stop_id: str) -> list[dict[str, Any]]:
        """Return cached service alerts attached to a stop's next departures."""
        digest = hashlib.sha256(stop_id.encode("utf-8")).hexdigest()[:20]
        cache_path = self._cache_dir / "alerts" / f"{digest}.json"
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
                "n": 5,
                "withAlerts": True,
                "language": "de",
            },
        )
        alerts: dict[str, dict[str, Any]] = {}
        stop_times = payload.get("stopTimes") if isinstance(payload, dict) else None
        for stop_time in _records(stop_times):
            place = stop_time.get("place")
            if not isinstance(place, dict):
                continue
            route_id = stop_time.get("routeId")
            for alert in _records(place.get("alerts")):
                header = str(alert.get("headerText") or "")
                code = str(alert.get("code") or header)
                existing = alerts.get(code)
                if existing is None:
                    existing = {
                        "code": code,
                        "header": header,
                        "description": str(alert.get("descriptionText") or ""),
                        "severity": str(alert.get("severityLevel") or "UNKNOWN"),
                        "url": (
                            alert.get("url") if isinstance(alert.get("url"), str) else None
                        ),
                        "routes": [],
                    }
                    alerts[code] = existing
                if isinstance(route_id, str) and route_id not in existing["routes"]:
                    existing["routes"].append(route_id)
        result = list(alerts.values())
        self._write_cache(cache_path, result)
        return result

    def search_places(
        self,
        text: str,
        *,
        limit: int | None = None,
        bias: tuple[float, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Return cached autocomplete results for stops and places in Germany."""
        query = text.strip()
        if len(query) < 2:
            return []

        count = limit or self._settings.transitous_geocode_limit
        bias_key = "" if bias is None else f"{bias[0]:.4f},{bias[1]:.4f}"
        digest = hashlib.sha256(
            f"{query.casefold()}|{count}|{bias_key}".encode()
        ).hexdigest()[:20]
        cache_path = self._cache_dir / "geocode" / f"{digest}.json"
        cached = self._read_cache(cache_path, CATALOG_TTL_SECONDS)
        if cached is not None:
            return _records(cached)

        params: dict[str, str | int | bool] = {
            "text": query,
            "numResults": count,
            "language": "de",
            "type": "STOP,ADDRESS,PLACE",
        }
        if bias is not None:
            params["place"] = f"{bias[0]},{bias[1]}"
            params["placeBias"] = 2

        try:
            payload = self._get("/v1/geocode", params=params)
        except ApiError:
            return []

        result: list[dict[str, Any]] = []
        for match in _records(payload):
            identifier, name = match.get("id"), match.get("name")
            lat, lon = match.get("lat"), match.get("lon")
            if not isinstance(identifier, str) or not isinstance(name, str):
                continue
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            result.append(
                {
                    "id": identifier,
                    "name": name,
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "type": str(match.get("type") or "STOP"),
                    "mode": str(match.get("category") or "").lower() or None,
                }
            )
        self._write_cache(cache_path, result)
        return result

    def search_connections(
        self,
        from_stop: str,
        to_stop: str,
        *,
        limit: int = 3,
        at: datetime | None = None,
        arrive_by: bool = False,
    ) -> list[dict[str, Any]]:
        """Search connections, with a 15-minute cache key and a daily request cap."""
        moment = at or self._now()
        bucket = moment.replace(
            minute=moment.minute - moment.minute % 15,
            second=0,
            microsecond=0,
        )
        key_source = (
            f"{from_stop}|{to_stop}|{bucket.isoformat()}|{int(arrive_by)}"
        )
        digest = hashlib.sha256(key_source.encode("utf-8")).hexdigest()[:20]
        cache_path = self._cache_dir / "connections" / f"{digest}.json"

        cached = self._read_cache(
            cache_path,
            self._settings.transitous_plan_cache_minutes * 60,
        )
        if cached is not None:
            return _records(cached)

        self._charge_plan_request()
        payload = self._get(
            "/v6/plan",
            params={
                "fromPlace": from_stop,
                "toPlace": to_stop,
                "time": moment.isoformat(),
                "arriveBy": arrive_by,
                "numItineraries": limit,
                "maxTransfers": 3,
                "searchWindow": 1800,
                "detailedLegs": False,
                "withFares": False,
                "realtimeMode": "REALTIME",
                "language": "de",
            },
        )
        if not isinstance(payload, dict):
            raise ApiError("Unexpected Transitous plan payload")
        itineraries = _records(payload.get("itineraries"))
        self._write_cache(cache_path, itineraries)
        return itineraries

    def _charge_plan_request(self) -> None:
        """Enforce a daily cap on the resource-heavy plan endpoint."""
        counter_path = self._cache_dir / "plan-counter.json"
        today = self._now().date().isoformat()
        count = 0
        try:
            document = json.loads(counter_path.read_text(encoding="utf-8"))
            body = document.get("payload", document) if isinstance(document, dict) else None
            if isinstance(body, dict) and body.get("date") == today:
                value = body.get("count")
                if isinstance(value, int):
                    count = value
        except (OSError, json.JSONDecodeError):
            pass

        if count >= self._settings.transitous_plan_limit_per_day:
            raise ApiError(
                "Daily connection search limit reached; "
                "try again tomorrow or raise TRANSITOUS_PLAN_LIMIT_PER_DAY"
            )

        self._write_cache(
            counter_path,
            {"date": today, "count": count + 1},
        )

    def _get(self, path: str, *, params: dict[str, str | int | bool]) -> object:
        for attempt in range(2):
            try:
                response = self._client.get(path, params=params)
                if attempt == 0 and response.status_code in RETRY_STATUSES:
                    time.sleep(1.0)
                    continue
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if (
                    attempt == 0
                    and exc.response.status_code in RETRY_STATUSES
                ):
                    time.sleep(1.0)
                    continue
                raise ApiError(f"Transitous request to {path} failed: {exc}") from exc
            except httpx.HTTPError as exc:
                raise ApiError(f"Transitous request to {path} failed: {exc}") from exc

            try:
                return response.json()
            except ValueError as exc:
                raise ApiError(f"Invalid JSON returned by {path}") from exc

        raise ApiError(f"Transitous request to {path} failed after retry")

    def _map_stop_time(
        self,
        stop_time: dict[str, Any],
        stop_id: str,
        arrive_by: bool,
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

        if arrive_by:
            scheduled = place.get("scheduledArrival") or place.get("scheduledDeparture")
            expected = place.get("arrival") or place.get("departure")
        else:
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
            "wheelchairAccessible": stop_time.get("wheelchairAccessible")
            if isinstance(stop_time.get("wheelchairAccessible"), bool)
            else None,
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

    def _read_cache_any(self, path: Path) -> object | None:
        """Return cached payload regardless of age, for offline fallback."""
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return document.get("payload") if isinstance(document, dict) else None

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
