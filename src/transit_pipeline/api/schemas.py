"""Pydantic response models for the kiosk UI."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Service and pipeline health for the status banner."""

    status: str
    database_ok: bool
    mock_mode: bool
    version: str
    stop_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    last_run_at: datetime | None = None
    last_run_status: str | None = None


class StopResponse(BaseModel):
    """A configured stop."""

    model_config = ConfigDict(from_attributes=True)

    stop_id: str
    name: str
    latitude: float | None = None
    longitude: float | None = None
    distance_m: int | None = None
    mode: str | None = None


class DepartureResponse(BaseModel):
    """A departure row for the live view."""

    model_config = ConfigDict(from_attributes=True)

    trip_id: str
    route_id: str
    route_short_name: str
    stop_id: str
    stop_name: str
    scheduled_time: datetime
    expected_time: datetime | None = None
    delay_seconds: int | None = None
    delay_category: str
    status: str
    mode: str | None = None


class RouteDelayResponse(BaseModel):
    """Worst observed delay for a route."""

    route_id: str
    route_short_name: str | None = None
    max_delay_seconds: int


class TransferRiskResponse(BaseModel):
    """A connection at risk at a stop."""

    model_config = ConfigDict(from_attributes=True)

    stop_id: str
    inbound_route_id: str
    outbound_route_id: str
    inbound_route_name: str | None = None
    outbound_route_name: str | None = None
    scheduled_transfer_seconds: int
    projected_slack_seconds: int
    at_risk: bool


class AlertResponse(BaseModel):
    """A service alert affecting a nearby stop."""

    code: str
    header: str
    description: str
    severity: str
    url: str | None = None
    stop_id: str | None = None


class ConnectionStopResponse(BaseModel):
    """An intermediate stop on a journey leg."""

    name: str
    arrival: datetime | None = None
    departure: datetime | None = None
    platform: str | None = None


class ConnectionLegResponse(BaseModel):
    """One leg of a planned connection."""

    mode: str
    route: str | None = None
    route_color: str | None = None
    headsign: str | None = None
    operator: str | None = None
    from_name: str
    to_name: str
    from_platform: str | None = None
    to_platform: str | None = None
    departure: datetime
    arrival: datetime
    intermediate_stops: list[ConnectionStopResponse] = Field(default_factory=list)


class ConnectionResponse(BaseModel):
    """A planned journey between two stops."""

    departure: datetime
    arrival: datetime
    duration_minutes: int
    transfers: int
    legs: list[ConnectionLegResponse]


class MetricsResponse(BaseModel):
    """Delay metrics and transfer risks for the delays and transfers views."""

    total_events: int = Field(ge=0)
    punctuality_rate: float = Field(ge=0.0, le=1.0)
    median_delay_seconds: float | None = None
    p95_delay_seconds: float | None = None
    top_delayed_routes: list[RouteDelayResponse]
    transfer_risks: list[TransferRiskResponse]
