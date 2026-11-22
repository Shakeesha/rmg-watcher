"""FastAPI routes for the kiosk UI and static frontend serving."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rmg_watcher import __version__
from rmg_watcher.api.schemas import (
    AlertResponse,
    ConnectionLegResponse,
    ConnectionResponse,
    ConnectionStopResponse,
    DepartureResponse,
    HealthResponse,
    MetricsResponse,
    PlaceResponse,
    RouteDelayResponse,
    StopResponse,
    TransferRiskResponse,
)
from rmg_watcher.config import Settings, get_settings
from rmg_watcher.constants import (
    DEFAULT_CONNECTION_LIMIT,
    DEFAULT_DEPARTURE_LIMIT,
    MAX_CONNECTIONS_PER_SEARCH,
    MAX_DEPARTURE_LIMIT,
    MAX_NEARBY_RADIUS_M,
    MAX_SUGGESTED_LIMIT,
    MAX_SUGGESTED_RADIUS_M,
    MIN_NEARBY_RADIUS_M,
    MIN_SUGGESTED_RADIUS_M,
    SECONDS_PER_MINUTE,
    STOP_CATALOG_FILE,
)
from rmg_watcher.domain.exceptions import ApiError
from rmg_watcher.ingestion.transitous import (
    TransitousClient,
    cached_stop_index,
    distance_meters,
    load_cached_stops,
)
from rmg_watcher.places import (
    find_stop,
    load_stop_catalog,
    search_stops,
    stop_name_key,
)
from rmg_watcher.storage.db import Database
from rmg_watcher.storage.repository import TransitRepository
from rmg_watcher.transform.deduplicator import deduplicate_departures
from rmg_watcher.transform.enricher import enrich_departures
from rmg_watcher.transform.validator import validate_departures


def get_repository(request: Request) -> TransitRepository:
    """Return the repository stored on the application state."""
    repository: TransitRepository = request.app.state.repository
    return repository


RepositoryDep = Annotated[TransitRepository, Depends(get_repository)]


def _as_datetime(value: object) -> datetime:
    fallback = datetime.now(UTC)
    if not isinstance(value, str) or not value:
        return fallback
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback


def _stop_mode(item: dict[str, object]) -> str | None:
    modes = item.get("modes")
    if isinstance(modes, list):
        for mode in modes:
            if isinstance(mode, str) and mode:
                return mode
    mode = item.get("mode")
    return mode if isinstance(mode, str) else None


def _catalog_stops(settings: Settings) -> list[dict[str, object]]:
    return load_cached_stops(settings.transitous_cache_path / STOP_CATALOG_FILE)


def _catalog_stop(
    settings: Settings,
    stop_id: str,
) -> dict[str, object] | None:
    return cached_stop_index(settings.transitous_cache_path / STOP_CATALOG_FILE).get(stop_id)


def _stop_location(
    stop_id: str,
    repo: TransitRepository,
    settings: Settings,
) -> tuple[float, float] | None:
    stop = repo.get_stop(stop_id)
    if stop is not None and stop.latitude is not None and stop.longitude is not None:
        return stop.latitude, stop.longitude
    item = _catalog_stop(settings, stop_id)
    if item is not None:
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
        key = stop_name_key(name)
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
                    mode=_stop_mode(item),
                ),
            )
        )
    result.sort(key=lambda entry: entry[0])
    return [stop for _, stop in result[:limit]]


def _stop_name(stop_id: str, repo: TransitRepository, settings: Settings) -> str:
    stop = repo.get_stop(stop_id)
    if stop is not None:
        return stop.name
    item = _catalog_stop(settings, stop_id)
    if item is not None and isinstance(item.get("name"), str):
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
        name_key = stop_name_key(name)
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
                    mode=_stop_mode(item),
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
    arrive_by: bool = False,
) -> list[DepartureResponse]:
    if settings.mock_mode or settings.transit_provider != "transitous":
        return [
            DepartureResponse.model_validate(departure)
            for departure in repo.list_departures(stop_id, limit=limit)
        ]

    client = TransitousClient(settings)
    try:
        raw = client.fetch_departures(stop_id, arrive_by=arrive_by)
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
                wheelchair_accessible=record.wheelchair_accessible,
            )
        )
    return result


def _connection_leg(
    leg: dict[str, Any],
    itinerary: dict[str, Any],
) -> ConnectionLegResponse | None:
    origin, destination = leg.get("from"), leg.get("to")
    if not isinstance(origin, dict) or not isinstance(destination, dict):
        return None

    intermediates: list[ConnectionStopResponse] = []
    raw_stops = leg.get("intermediateStops")
    if isinstance(raw_stops, list):
        for stop in raw_stops:
            if not isinstance(stop, dict):
                continue
            intermediates.append(
                ConnectionStopResponse(
                    name=str(stop.get("name") or ""),
                    arrival=_as_datetime(stop["arrival"]) if stop.get("arrival") else None,
                    departure=(
                        _as_datetime(stop["departure"]) if stop.get("departure") else None
                    ),
                    platform=str(stop["track"]) if stop.get("track") else None,
                )
            )

    mode = leg.get("mode")
    route_id = leg.get("routeId")
    route = leg.get("routeShortName") or leg.get("displayName")
    color = leg.get("routeColor")
    operator = leg.get("agencyName")
    headsign = leg.get("headsign")

    return ConnectionLegResponse(
        mode=str(mode).lower() if mode is not None else "transit",
        route_id=str(route_id) if isinstance(route_id, str) else None,
        route=str(route) if route is not None else None,
        route_color=str(color) if isinstance(color, str) else None,
        headsign=str(headsign) if isinstance(headsign, str) else None,
        operator=str(operator) if isinstance(operator, str) else None,
        from_name=str(origin.get("name") or ""),
        to_name=str(destination.get("name") or ""),
        from_platform=str(origin["track"]) if origin.get("track") else None,
        to_platform=str(destination["track"]) if destination.get("track") else None,
        departure=_as_datetime(leg.get("startTime") or itinerary.get("startTime")),
        arrival=_as_datetime(leg.get("endTime") or itinerary.get("endTime")),
        intermediate_stops=intermediates,
    )


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

    if time is not None and time.tzinfo is None:
        time = time.replace(tzinfo=UTC)

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
            parsed = _connection_leg(leg, itinerary)
            if parsed is not None:
                legs.append(parsed)
        result.append(
            ConnectionResponse(
                departure=_as_datetime(itinerary.get("startTime")),
                arrival=_as_datetime(itinerary.get("endTime")),
                duration_minutes=int(itinerary.get("duration") or 0) // SECONDS_PER_MINUTE,
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
        try:
            for stop_id in stop_ids[: settings.transitous_alert_stops]:
                for alert in client.fetch_alerts(stop_id):
                    key = f"{stop_id}:{alert.get('code')}"
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append(AlertResponse(stop_id=stop_id, **alert))
        except ApiError:
            # Alerts are non-critical; a transient upstream failure should not
            # break the kiosk or surface a raw 502 to the user.
            return []
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
        title="RMG-Watcher",
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
        radius: int = Query(
            default=app_settings.transitous_suggested_radius_m,
            ge=MIN_SUGGESTED_RADIUS_M,
            le=MAX_SUGGESTED_RADIUS_M,
        ),
        limit: int = Query(
            default=app_settings.transitous_suggested_limit,
            ge=1,
            le=MAX_SUGGESTED_LIMIT,
        ),
    ) -> list[StopResponse]:
        latitude = lat if lat is not None else app_settings.transitous_home_lat
        longitude = lon if lon is not None else app_settings.transitous_home_lon
        return _suggested_stops(app_settings, latitude, longitude, radius, limit)

    @app.get(
        "/api/places",
        response_model=list[PlaceResponse],
        tags=["stops"],
    )
    def places(q: str = Query(default="", min_length=2)) -> list[PlaceResponse]:
        local = search_stops(
            load_stop_catalog(app_settings.german_stops_path),
            q,
            app_settings.transitous_geocode_limit,
        )
        if local:
            return [PlaceResponse(**place) for place in local]
        if app_settings.mock_mode or app_settings.transit_provider != "transitous":
            return []
        client = TransitousClient(app_settings)
        try:
            return [PlaceResponse(**place) for place in client.search_places(q)]
        except ApiError:
            return []
        finally:
            client.close()

    @app.get(
        "/api/places/resolve",
        response_model=PlaceResponse | None,
        tags=["stops"],
    )
    def resolve_place(id: str = Query(min_length=1)) -> PlaceResponse | None:
        stop = find_stop(load_stop_catalog(app_settings.german_stops_path), id)
        if stop is None or app_settings.mock_mode:
            return None
        client = TransitousClient(app_settings)
        try:
            matches = client.search_places(
                str(stop["name"]),
                limit=1,
                bias=(float(stop["latitude"]), float(stop["longitude"])),
            )
        except ApiError:
            return None
        finally:
            client.close()
        return PlaceResponse(**matches[0]) if matches else None

    @app.get(
        "/api/stops/nearby/{stop_id}",
        response_model=list[StopResponse],
        tags=["stops"],
    )
    def nearby_stops(
        stop_id: str,
        repo: RepositoryDep,
        radius: int = Query(
            default=app_settings.transitous_nearby_radius_m,
            ge=MIN_NEARBY_RADIUS_M,
            le=MAX_NEARBY_RADIUS_M,
        ),
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
        limit: int = Query(
            default=DEFAULT_DEPARTURE_LIMIT, ge=1, le=MAX_DEPARTURE_LIMIT
        ),
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
        limit: int = Query(
            default=DEFAULT_DEPARTURE_LIMIT, ge=1, le=MAX_DEPARTURE_LIMIT
        ),
        arrive_by: bool = Query(default=False),
    ) -> list[DepartureResponse]:
        try:
            return _live_departures(stop_id, limit, repo, app_settings, arrive_by)
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
        limit: int = Query(
            default=DEFAULT_CONNECTION_LIMIT, ge=1, le=MAX_CONNECTIONS_PER_SEARCH
        ),
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
        summary, risks = repo.metrics_and_risks()
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
