"""Tests for the cached, low-rate Transitous client."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from rmg_watcher.config import Settings
from rmg_watcher.domain.exceptions import ApiError
from rmg_watcher.ingestion.transitous import TransitousClient

BASE = "https://api.transitous.org/api"


@pytest.fixture
def transitous_settings(tmp_path: Path) -> Settings:
    return Settings(
        mock_mode=True,
        transit_provider="transitous",
        transitous_contact="dev@example.com",
        transitous_cache_path=tmp_path / "cache",
        transitous_watch_stops=("de:06411:4734",),
        transitous_min_refresh_seconds=600,
        _env_file=None,
    )


def _stop_payload(name: str, stop_id: str, lat: float, lon: float) -> dict[str, Any]:
    return {"name": name, "stopId": stop_id, "lat": lat, "lon": lon}


def _stop_time(
    trip_id: str = "trip-1",
    *,
    cancelled: bool = False,
) -> dict[str, Any]:
    return {
        "tripId": trip_id,
        "routeId": "route-4",
        "routeShortName": "4",
        "mode": "TRAM",
        "realTime": True,
        "cancelled": cancelled,
        "tripCancelled": False,
        "place": {
            "scheduledDeparture": "2026-11-22T10:00:00Z",
            "departure": "2026-11-22T10:05:00Z",
        },
    }


@respx.mock
def test_fetch_stops_deduplicates_and_caches(
    transitous_settings: Settings,
) -> None:
    route = respx.get(f"{BASE}/v6/map/stops").mock(
        return_value=httpx.Response(
            200,
            json=[
                _stop_payload("Darmstadt Hbf", "de:06411:4734", 49.8725, 8.6296),
                _stop_payload("Darmstadt Hbf", "de:06411:4734:1:1", 49.8725, 8.6296),
            ],
        )
    )

    with TransitousClient(transitous_settings) as client:
        first = client.fetch_stops()
        second = client.fetch_stops()

    assert route.call_count == 1
    assert first == second
    assert len(first) == 1
    assert first[0]["stopId"] == "de:06411:4734"
    assert "dev@example.com" in route.calls[0].request.headers["user-agent"]


@respx.mock
def test_fetch_departures_maps_fields_and_caches(
    transitous_settings: Settings,
) -> None:
    route = respx.get(f"{BASE}/v6/stoptimes").mock(
        return_value=httpx.Response(
            200,
            json={
                "stopTimes": [
                    _stop_time(),
                    _stop_time("trip-2", cancelled=True),
                ]
            },
        )
    )

    with TransitousClient(transitous_settings) as client:
        first = client.fetch_departures("de:06411:4734")
        second = client.fetch_departures("de:06411:4734")

    assert route.call_count == 1
    assert first == second
    assert first[0]["tripId"] == "trip-1"
    assert first[0]["routeShortName"] == "4"
    assert first[0]["scheduledTime"] == "2026-11-22T10:00:00Z"
    assert first[0]["expectedTime"] == "2026-11-22T10:05:00Z"
    assert first[0]["status"] == "delayed"
    assert first[0]["routeMode"] == "tram"
    assert first[1]["status"] == "cancelled"


@respx.mock
def test_fetch_departures_returns_no_realtime_estimate_without_rt_flag(
    transitous_settings: Settings,
) -> None:
    payload = _stop_time()
    payload["realTime"] = False
    respx.get(f"{BASE}/v6/stoptimes").mock(
        return_value=httpx.Response(200, json={"stopTimes": [payload]})
    )

    with TransitousClient(transitous_settings) as client:
        records = client.fetch_departures("de:06411:4734")

    assert records[0]["expectedTime"] is None
    assert records[0]["status"] == "on_time"


def test_client_requires_a_contact(transitous_settings: Settings) -> None:
    settings = transitous_settings.model_copy(update={"transitous_contact": None})

    with pytest.raises(ApiError, match="TRANSIT_CONTACT"):
        TransitousClient(settings)


@respx.mock
def test_connections_cache_and_daily_cap(transitous_settings: Settings) -> None:
    settings = transitous_settings.model_copy(
        update={"transitous_plan_limit_per_day": 1}
    )
    route = respx.get(f"{BASE}/v6/plan").mock(
        return_value=httpx.Response(200, json={"itineraries": [{"id": "it-1"}]})
    )
    now = datetime(2026, 11, 22, 10, 7, tzinfo=UTC)

    with TransitousClient(settings) as client:
        first = client.search_connections("a", "b", at=now)
        second = client.search_connections("a", "b", at=now)

        assert first == second
        assert route.call_count == 1

        with pytest.raises(ApiError, match="Daily connection search limit"):
            client.search_connections("b", "c", at=now)
