"""Tests for FastAPI endpoints against an isolated test database."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rmg_watcher.api.app import create_app
from rmg_watcher.config import Settings
from rmg_watcher.pipeline import run_pipeline
from rmg_watcher.storage.db import Database
from rmg_watcher.storage.repository import TransitRepository


@pytest.fixture
def repository(settings: Settings) -> TransitRepository:
    run_pipeline(settings, batch_id="api-seed")
    return TransitRepository(Database(settings.database_path))


@pytest.fixture
def client(settings: Settings, repository: TransitRepository) -> Iterator[TestClient]:
    app = create_app(settings=settings, repository=repository)
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_pipeline_state(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database_ok"] is True
    assert body["mock_mode"] is True
    assert body["stop_count"] == 2
    assert body["event_count"] == 7
    assert body["last_run_status"] == "ok"


def test_map_tile_rejects_invalid_coordinates(client: TestClient) -> None:
    assert client.get("/api/tiles/16/99999/1.png").status_code == 404
    assert client.get("/api/tiles/99/1/1.png").status_code == 404
    assert client.get("/api/tiles/16/-1/1.png").status_code == 404


def test_map_tile_serves_cached_file(client: TestClient, settings: Settings) -> None:
    tile = settings.transitous_cache_path / "tiles" / "16" / "34454" / "22365.png"
    tile.parent.mkdir(parents=True, exist_ok=True)
    tile.write_bytes(b"cached-png")

    response = client.get("/api/tiles/16/34454/22365.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"cached-png"


def test_stops_are_sorted_by_name(client: TestClient) -> None:
    response = client.get("/api/stops")

    assert response.status_code == 200
    names = [stop["name"] for stop in response.json()]
    assert names == ["Darmstadt Hauptbahnhof", "Darmstadt Luisenplatz"]


def test_departures_include_delay_information(client: TestClient) -> None:
    response = client.get("/api/departures/luisenplatz")

    assert response.status_code == 200
    departures = response.json()
    assert len(departures) == 4
    assert departures[0]["trip_id"] == "trip-1001"
    assert departures[0]["delay_seconds"] == 240
    assert departures[0]["delay_category"] == "minor"


def test_departures_support_a_limit(client: TestClient) -> None:
    response = client.get("/api/departures/luisenplatz?limit=2")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_unknown_stop_returns_404(client: TestClient) -> None:
    response = client.get("/api/departures/unknown")

    assert response.status_code == 404


def test_metrics_include_transfer_risks(client: TestClient) -> None:
    response = client.get("/api/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] == 7
    assert body["top_delayed_routes"][0] == {
        "route_id": "route-H",
        "route_short_name": "H",
        "max_delay_seconds": 1200,
    }
    assert body["transfer_risks"]
    assert body["transfer_risks"][0]["at_risk"] is True


def test_missing_frontend_reports_build_hint(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "Frontend bundle not built"


def test_built_frontend_is_served(
    settings: Settings,
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>kiosk</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    app = create_app(settings=settings.model_copy(update={"frontend_dist_path": dist}))

    with TestClient(app) as test_client:
        assert test_client.get("/").text == "<html>kiosk</html>"
        assert test_client.get("/assets/app.js").text == "console.log('ok')"
        assert test_client.get("/unknown-route").text == "<html>kiosk</html>"


def test_nearby_stops_use_cached_catalog(
    settings: Settings,
    repository: TransitRepository,
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "transitous"
    cache_dir.mkdir()
    (cache_dir / "stops.json").write_text(
        json.dumps(
            {
                "fetched_at": "2026-11-22T00:00:00+00:00",
                "payload": [
                    {
                        "stopId": "luisenplatz",
                        "name": "Darmstadt Luisenplatz",
                        "latitude": 49.872881,
                        "longitude": 8.651252,
                    },
                    {
                        "stopId": "near-stop",
                        "name": "Luisenplatz Nord",
                        "latitude": 49.8734,
                        "longitude": 8.6520,
                    },
                    {
                        "stopId": "far-stop",
                        "name": "Babenhausen Bahnhof",
                        "latitude": 49.957962,
                        "longitude": 8.957182,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    app = create_app(
        settings=settings.model_copy(update={"transitous_cache_path": cache_dir}),
        repository=repository,
    )

    with TestClient(app) as test_client:
        response = test_client.get("/api/stops/nearby/luisenplatz?radius=1000")

    assert response.status_code == 200
    stops = response.json()
    assert [stop["stop_id"] for stop in stops] == ["near-stop"]
    assert stops[0]["distance_m"] is not None
    assert stops[0]["distance_m"] > 0


def test_live_departures_endpoint_uses_stored_data_in_mock_mode(
    settings: Settings,
    repository: TransitRepository,
) -> None:
    app = create_app(settings=settings, repository=repository)

    with TestClient(app) as test_client:
        response = test_client.get("/api/departures/live/luisenplatz?limit=2")

    assert response.status_code == 200
    departures = response.json()
    assert len(departures) == 2
    assert departures[0]["trip_id"] == "trip-1001"


def test_connections_endpoint_is_empty_in_mock_mode(
    settings: Settings,
    repository: TransitRepository,
) -> None:
    app = create_app(settings=settings, repository=repository)

    with TestClient(app) as test_client:
        response = test_client.get("/api/connections?from=luisenplatz&to=hbf")

    assert response.status_code == 200
    assert response.json() == []


def test_suggested_stops_are_deduplicated(
    settings: Settings,
    repository: TransitRepository,
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "transitous"
    cache_dir.mkdir()
    (cache_dir / "stops.json").write_text(
        json.dumps(
            {
                "fetched_at": "2026-11-22T00:00:00+00:00",
                "payload": [
                    {
                        "stopId": "near",
                        "name": "Luisenplatz",
                        "latitude": 49.873,
                        "longitude": 8.651,
                    },
                    {
                        "stopId": "near-platform",
                        "name": "Luisenplatz",
                        "latitude": 49.8731,
                        "longitude": 8.6511,
                    },
                    {
                        "stopId": "far",
                        "name": "Babenhausen Bahnhof",
                        "latitude": 49.958,
                        "longitude": 8.957,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    app = create_app(
        settings=settings.model_copy(update={"transitous_cache_path": cache_dir}),
        repository=repository,
    )

    with TestClient(app) as test_client:
        response = test_client.get("/api/stops/suggested?lat=49.872881&lon=8.651252&radius=1500")

    assert response.status_code == 200
    stops = response.json()
    assert [stop["stop_id"] for stop in stops] == ["near"]
    assert stops[0]["distance_m"] is not None


def test_alerts_endpoint_is_empty_in_mock_mode(
    settings: Settings,
    repository: TransitRepository,
) -> None:
    app = create_app(settings=settings, repository=repository)

    with TestClient(app) as test_client:
        response = test_client.get("/api/alerts")

    assert response.status_code == 200
    assert response.json() == []
