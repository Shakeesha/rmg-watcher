"""Core domain models: Stop, Route, DelayEvent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TripStatus(StrEnum):
    """Status of a trip at a stop."""

    ON_TIME = "on_time"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class DelayCategory(StrEnum):
    """Bucketed delay severity used by the kiosk UI and metrics."""

    ON_TIME = "on_time"
    MINOR = "minor"
    MAJOR = "major"
    SEVERE = "severe"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Stop:
    """A transit stop."""

    stop_id: str
    name: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True, slots=True)
class Route:
    """A transit route or line."""

    route_id: str
    short_name: str
    long_name: str | None = None
    mode: str = "unknown"


@dataclass(frozen=True, slots=True)
class DelayEvent:
    """A validated departure enriched with delay information."""

    trip_id: str
    route_id: str
    stop_id: str
    scheduled_time: datetime
    expected_time: datetime | None
    delay_seconds: int | None
    delay_category: DelayCategory
    status: TripStatus
    observed_at: datetime
