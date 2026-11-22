"""FastAPI routes for the kiosk UI and static frontend serving."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from transit_pipeline import __version__
from transit_pipeline.api.schemas import (
    AlertResponse,
    ConnectionLegResponse,
    ConnectionResponse,
    DepartureResponse,
    HealthResponse,
    MetricsResponse,
    RouteDelayResponse,
    StopResponse,
    TransferRiskResponse,
)
from transit_pipeline.config import Settings, get_settings
from transit_pipeline.domain.exceptions import ApiError
from transit_pipeline.ingestion.transitous import (
    TransitousClient,
    distance_meters,
    load_cached_stops,
    normalize_stop_name,
)
from transit_pipeline.storage.db import Database
from transit_pipeline.storage.repository import TransitRepository
from transit_pipeline.transform.deduplicator import deduplicate_departures
from transit_pipeline.transform.enricher import enrich_departures
from transit_pipeline.transform.validator import validate_departures


def get_repository(request: Request) -> TransitRepository:
    """Return the repository stored on the application state."""
    repository: TransitRepository = request.app.state.repository
    return repository


RepositoryDep = Annotated[TransitRepository, Depends(get_repository)]


def _as_datetime(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(UTC)


def _catalog_stops(settings: Settings) -> list[dict[str, object]]:
    return load_cached_stops(settings.transitous_cache_path / "stops.json")


def _stop_location(
    stop_id: str,
    repo: TransitRepository,
    settings: Settings,
) -> tuple[float, float] | None:
    stop = repo.get_stop(stop_id)
    if stop is not None and stop.latitude is not None and stop.longitude is not None:
        return stop.latitude, stop.longitude
    for item in _catalog_stops(settings):
        if item.get("stopId") != stop_id:
            continue
        lat, lon = item.get("latitude"), item.get("longitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon)
    return None


def _suggested_stops(
    settings: Settings,
    latitude: float,
    longitude: float,
    radius: int,
    limit: int,
) -> list[StopResponse]:
    seen: set[str] = set()
    result: list[tuple[int, StopResponse]] = []
    for item in _catalog_stops(settings):
        name = item.get("name")
        lat, lon = item.get("latitude"), item.get("longitude")
        if not isinstance(name, str) or not isinstance(lat, (int, float)):
            continue
        if not isinstance(lon, (int, float)):
            continue
        key = normalize_stop_name(name)
        if key in seen:
            continue
        distance = distance_meters(latitude, longitude, float(lat), float(lon))
        if distance > radius:
            continue
        seen.add(key)
        result.append(
            (
                distance,
                StopResponse(
                    stop_id=str(item["stopId"]),
                    name=name,
                    latitude=float(lat),
                    longitude=float(lon),
                    distance_m=distance,
                ),
            )
        )
    result.sort(key=lambda entry: entry[0])
    return [stop for _, stop in result[:limit]]


def _stop_name(stop_id: str, repo: TransitRepository, settings: Settings) -> str:
    stop = repo.get_stop(stop_id)
    if stop is not None:
        return stop.name
    for item in _catalog_stops(settings):
        if item.get("stopId") == stop_id and isinstance(item.get("name"), str):
            return str(item["name"])
    return stop_id


def _nearby_stops(
    stop_id: str,
    repo: TransitRepository,
    settings: Settings,
) -> list[StopResponse]:
    location = _stop_location(stop_id, repo, settings)
    if location is None:
        return []

    candidates: list[dict[str, object]]
    catalog = _catalog_stops(settings)
    candidates = catalog if catalog else [
        {
            "stopId": stop.stop_id,
            "name": stop.name,
            "latitude": stop.latitude,
            "longitude": stop.longitude,
        }
        for stop in repo.list_stops()
    ]

    nearby: list[tuple[int, StopResponse]] = []
    seen: dict[str, int] = {}
    for item in candidates:
        if item.get("stopId") == stop_id:
            continue
        lat, lon = item.get("latitude"), item.get("longitude")
        name = item.get("name")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        if not isinstance(name, str) or not name:
            continue
        distance = distance_meters(
            location[0],
            location[1],
            float(lat),
            float(lon),
        )
        if distance > settings.transitous_nearby_radius_m:
            continue
        name_key = normalize_stop_name(name)
        if name_key in seen and seen[name_key] <= distance:
            continue
        seen[name_key] = distance
        nearby.append(
            (
                distance,
                StopResponse(
                    stop_id=str(item["stopId"]),
                    name=name,
                    latitude=float(lat),
                    longitude=float(lon),
                    distance_m=distance,
                ),
            )
        )

    nearby.sort(key=lambda entry: entry[0])
    return [stop for _, stop in nearby[: settings.transitous_nearby_limit]]


def _live_departures(
    stop_id: str,
    limit: int,
    repo: TransitRepository,
    settings: Settings,
) -> list[DepartureResponse]:
    if settings.mock_mode or settings.transit_provider != "transitous":
        return [
            DepartureResponse.model_validate(departure)
            for departure in repo.list_departures(stop_id, limit=limit)
        ]

    client = TransitousClient(settings)
    try:
        raw = client.fetch_departures(stop_id)
    finally:
        client.close()

    validation = validate_departures(raw, batch_id=f"live-{stop_id}")
    unique, _ = deduplicate_departures(validation.valid)
    events = enrich_departures(unique)
    by_trip = {event.trip_id: event for event in events}
    stop_name = _stop_name(stop_id, repo, settings)

    result: list[DepartureResponse] = []
    for record in unique[:limit]:
        event = by_trip[record.trip_id]
        result.append(
            DepartureResponse(
                trip_id=record.trip_id,
                route_id=record.route_id,
                route_short_name=record.route_short_name or record.route_id,
                stop_id=stop_id,
                stop_name=stop_name,
                scheduled_time=record.scheduled_time,
                expected_time=record.expected_time,
                delay_seconds=event.delay_seconds,
                delay_category=event.delay_category.value,
                status=event.status.value,
                mode=record.route_mode,
            )
        )
    return result


def _connections(
    from_stop: str,
    to_stop: str,
    limit: int,
    settings: Settings,
    time: datetime | None = None,
    arrive_by: bool = False,
) -> list[ConnectionResponse]:
    if settings.mock_mode or settings.transit_provider != "transitous":
        return []

    client = TransitousClient(settings)
    try:
        itineraries = client.search_connections(
            from_stop,
            to_stop,
            limit=limit,
            at=time,
            arrive_by=arrive_by,
        )
    finally:
        client.close()

    result: list[ConnectionResponse] = []
    for itinerary in itineraries:
        legs: list[ConnectionLegResponse] = []
        for leg in itinerary.get("legs", []):
            if not isinstance(leg, dict):
                continue
            origin, destination = leg.get("from"), leg.get("to")
            if not isinstance(origin, dict) or not isinstance(destination, dict):
                continue
            mode = leg.get("mode")
            route = leg.get("routeShortName") or leg.get("displayName")
            legs.append(
                ConnectionLegResponse(
                    mode=str(mode).lower() if mode is not None else "transit",
                    route=str(route) if route is not None else None,
                    from_name=str(origin.get("name") or ""),
                    to_name=str(destination.get("name") or ""),
                    departure=_as_datetime(
                        leg.get("startTime") or itinerary.get("startTime")
                    ),
                    arrival=_as_datetime(leg.get("endTime") or itinerary.get("endTime")),
                )
            )
        result.append(
            ConnectionResponse(
                departure=_as_datetime(itinerary.get("startTime")),
                arrival=_as_datetime(itinerary.get("endTime")),
                duration_minutes=int(itinerary.get("duration") or 0) // 60,
                transfers=int(itinerary.get("transfers") or 0),
                legs=legs,
            )
        )
    return result


def _alerts(
    stop_ids: list[str],
    settings: Settings,
) -> list[AlertResponse]:
    if settings.mock_mode or settings.transit_provider != "transitous":
        return []

    client = TransitousClient(settings)
    try:
        result: list[AlertResponse] = []
        seen: set[str] = set()
        for stop_id in stop_ids[: settings.transitous_alert_stops]:
            for alert in client.fetch_alerts(stop_id):
                key = f"{stop_id}:{alert.get('code')}"
                if key in seen:
                    continue
                seen.add(key)
                result.append(AlertResponse(stop_id=stop_id, **alert))
        return result
    finally:
        client.close()


def create_app(
    settings: Settings | None = None,
    repository: TransitRepository | None = None,
) -> FastAPI:
    """Build the FastAPI application, optionally with injected dependencies."""
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if repository is None:
            database = Database(app_settings.database_path)
            database.initialize()
            app.state.repository = TransitRepository(database)
        else:
            repository.database.initialize()
            app.state.repository = repository
        yield

    app = FastAPI(
        title="Transit Telemetry",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = app_settings

    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    def health(repo: RepositoryDep) -> HealthResponse:
        try:
            stop_count = repo.count_stops()
            event_count = repo.count_events()
            latest = repo.latest_run()
        except sqlite3.Error:
            return HealthResponse(
                status="degraded",
                database_ok=False,
                mock_mode=app_settings.mock_mode,
                version=__version__,
                stop_count=0,
                event_count=0,
            )

        return HealthResponse(
            status="ok",
            database_ok=True,
            mock_mode=app_settings.mock_mode,
            version=__version__,
            stop_count=stop_count,
            event_count=event_count,
            last_run_at=(
                latest.finished_at or latest.started_at if latest is not None else None
            ),
            last_run_status=latest.status if latest is not None else None,
        )

    @app.get("/api/stops", response_model=list[StopResponse], tags=["stops"])
    def list_stops(repo: RepositoryDep) -> list[StopResponse]:
        return [StopResponse.model_validate(stop) for stop in repo.list_stops()]

    @app.get(
        "/api/stops/suggested",
        response_model=list[StopResponse],
        tags=["stops"],
    )
    def suggested_stops(
        lat: float | None = Query(default=None),
        lon: float | None = Query(default=None),
        radius: int = Query(default=1500, ge=100, le=10000),
        limit: int = Query(default=8, ge=1, le=20),
    ) -> list[StopResponse]:
        latitude = lat if lat is not None else app_settings.transitous_home_lat
        longitude = lon if lon is not None else app_settings.transitous_home_lon
        return _suggested_stops(app_settings, latitude, longitude, radius, limit)

    @app.get(
        "/api/stops/nearby/{stop_id}",
        response_model=list[StopResponse],
        tags=["stops"],
    )
    def nearby_stops(
        stop_id: str,
        repo: RepositoryDep,
        radius: int = Query(default=1000, ge=50, le=5000),
    ) -> list[StopResponse]:
        effective = app_settings.model_copy(update={"transitous_nearby_radius_m": radius})
        return _nearby_stops(stop_id, repo, effective)

    @app.get(
        "/api/departures/{stop_id}",
        response_model=list[DepartureResponse],
        tags=["departures"],
    )
    def list_departures(
        stop_id: str,
        repo: RepositoryDep,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[DepartureResponse]:
        if repo.get_stop(stop_id) is None:
            raise HTTPException(status_code=404, detail=f"Unknown stop: {stop_id}")
        return [
            DepartureResponse.model_validate(departure)
            for departure in repo.list_departures(stop_id, limit=limit)
        ]

    @app.get(
        "/api/departures/live/{stop_id}",
        response_model=list[DepartureResponse],
        tags=["departures"],
    )
    def live_departures(
        stop_id: str,
        repo: RepositoryDep,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[DepartureResponse]:
        try:
            return _live_departures(stop_id, limit, repo, app_settings)
        except ApiError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get(
        "/api/alerts",
        response_model=list[AlertResponse],
        tags=["alerts"],
    )
    def alerts(stop_id: str | None = Query(default=None)) -> list[AlertResponse]:
        if stop_id:
            stop_ids = [stop_id]
        else:
            stop_ids = [
                stop.stop_id
                for stop in _suggested_stops(
                    app_settings,
                    app_settings.transitous_home_lat,
                    app_settings.transitous_home_lon,
                    app_settings.transitous_suggested_radius_m,
                    app_settings.transitous_suggested_limit,
                )
            ]
        try:
            return _alerts(stop_ids, app_settings)
        except ApiError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get(
        "/api/connections",
        response_model=list[ConnectionResponse],
        tags=["connections"],
    )
    def connections(
        from_stop: str = Query(alias="from"),
        to_stop: str = Query(alias="to"),
        limit: int = Query(default=3, ge=1, le=5),
        time: Annotated[datetime | None, Query()] = None,
        arrive_by: bool = Query(default=False),
    ) -> list[ConnectionResponse]:
        if not from_stop.strip() or not to_stop.strip():
            raise HTTPException(status_code=400, detail="from and to are required")
        try:
            return _connections(
                from_stop,
                to_stop,
                limit,
                app_settings,
                time=time,
                arrive_by=arrive_by,
            )
        except ApiError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/metrics", response_model=MetricsResponse, tags=["metrics"])
    def metrics(repo: RepositoryDep) -> MetricsResponse:
        summary = repo.metrics_summary()
        risks = repo.transfer_risks()
        return MetricsResponse(
            total_events=summary.total_events,
            punctuality_rate=summary.punctuality_rate,
            median_delay_seconds=summary.median_delay_seconds,
            p95_delay_seconds=summary.p95_delay_seconds,
            top_delayed_routes=[
                RouteDelayResponse(
                    route_id=route_id,
                    route_short_name=summary.route_names.get(route_id) or route_id,
                    max_delay_seconds=delay,
                )
                for route_id, delay in summary.top_delayed_routes
            ],
            transfer_risks=[
                TransferRiskResponse.model_validate(risk) for risk in risks
            ],
        )

    _mount_frontend(app, app_settings.frontend_dist_path)
    return app


def _mount_frontend(app: FastAPI, frontend_dir: Path) -> None:
    if not frontend_dir.is_dir():
        @app.get("/", include_in_schema=False)
        def frontend_missing() -> dict[str, str]:
            return {
                "message": "Frontend bundle not built",
                "docs": "/docs",
            }

        return

    resolved_root = frontend_dir.resolve()
    assets_dir = resolved_root / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    index_path = resolved_root / "index.html"

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (resolved_root / path).resolve()
        if candidate.is_file() and candidate.is_relative_to(resolved_root):
            return FileResponse(candidate)
        return FileResponse(index_path)


app = create_app()
