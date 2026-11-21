"""FastAPI routes for the kiosk UI and static frontend serving."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from transit_pipeline import __version__
from transit_pipeline.api.schemas import (
    DepartureResponse,
    HealthResponse,
    MetricsResponse,
    RouteDelayResponse,
    StopResponse,
    TransferRiskResponse,
)
from transit_pipeline.config import Settings, get_settings
from transit_pipeline.storage.db import Database
from transit_pipeline.storage.repository import TransitRepository


def get_repository(request: Request) -> TransitRepository:
    """Return the repository stored on the application state."""
    repository: TransitRepository = request.app.state.repository
    return repository


RepositoryDep = Annotated[TransitRepository, Depends(get_repository)]


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
                RouteDelayResponse(route_id=route_id, max_delay_seconds=delay)
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
