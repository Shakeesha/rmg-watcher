"""Schema and plausibility validation that splits valid records from quarantine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from rmg_watcher.domain.models import TripStatus

MAX_EARLY_SECONDS = 3_600
MAX_LATE_SECONDS = 12 * 3_600


@dataclass(frozen=True, slots=True)
class ValidDeparture:
    """A raw departure that passed validation."""

    trip_id: str
    route_id: str
    stop_id: str
    scheduled_time: datetime
    expected_time: datetime | None
    status: TripStatus
    route_short_name: str | None = None
    route_mode: str | None = None
    wheelchair_accessible: bool | None = None


@dataclass(frozen=True, slots=True)
class QuarantinedRecord:
    """A rejected record with its reason and original payload."""

    batch_id: str
    record_hash: str
    reason: str
    payload: Mapping[str, Any]
    quarantined_at: datetime


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """The valid and quarantined halves of a raw batch."""

    valid: list[ValidDeparture]
    quarantined: list[QuarantinedRecord]


class DeparturePayload(BaseModel):
    """Validated shape of one raw departure payload."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        str_strip_whitespace=True,
    )

    trip_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("tripId", "trip_id"),
    )
    route_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("routeId", "route_id"),
    )
    stop_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("stopId", "stop_id"),
    )
    scheduled_time: datetime = Field(
        validation_alias=AliasChoices("scheduledTime", "scheduled_time"),
    )
    expected_time: datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("expectedTime", "expected_time"),
    )
    status: TripStatus = Field(default=TripStatus.UNKNOWN)
    route_short_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("routeShortName", "route_short_name"),
    )
    route_mode: str | None = Field(
        default=None,
        validation_alias=AliasChoices("routeMode", "route_mode"),
    )
    wheelchair_accessible: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("wheelchairAccessible", "wheelchair_accessible"),
    )

    @field_validator("status", mode="before")
    @classmethod
    def _normalise_status(cls, value: object) -> object:
        if value is None:
            return TripStatus.UNKNOWN
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "canceled": TripStatus.CANCELLED,
            "cancelled": TripStatus.CANCELLED,
            "delay": TripStatus.DELAYED,
            "delayed": TripStatus.DELAYED,
            "ontime": TripStatus.ON_TIME,
            "on_time": TripStatus.ON_TIME,
        }
        return aliases.get(text, TripStatus.UNKNOWN)

    @field_validator("scheduled_time", "expected_time", mode="after")
    @classmethod
    def _ensure_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @model_validator(mode="after")
    def _check_plausibility(self) -> Self:
        if self.expected_time is None:
            return self
        delta = (self.expected_time - self.scheduled_time).total_seconds()
        if delta < -MAX_EARLY_SECONDS:
            raise ValueError("expected_time is implausibly earlier than scheduled_time")
        if delta > MAX_LATE_SECONDS:
            raise ValueError("expected_time is implausibly later than scheduled_time")
        return self


def hash_record(record: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 hash of a raw record."""
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reason_for(error: ValidationError) -> str:
    parts: list[str] = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "record"
        parts.append(f"{location}: {detail['msg']}")
    return "; ".join(parts)


def validate_departures(
    records: Sequence[Mapping[str, Any]],
    *,
    batch_id: str,
    quarantined_at: datetime | None = None,
) -> ValidationResult:
    """Validate raw departures, routing invalid records to quarantine."""
    valid: list[ValidDeparture] = []
    quarantined: list[QuarantinedRecord] = []
    timestamp = quarantined_at or datetime.now(UTC)

    for record in records:
        try:
            payload = DeparturePayload.model_validate(record)
        except ValidationError as exc:
            quarantined.append(
                QuarantinedRecord(
                    batch_id=batch_id,
                    record_hash=hash_record(record),
                    reason=_reason_for(exc),
                    payload=record,
                    quarantined_at=timestamp,
                )
            )
            continue

        valid.append(
            ValidDeparture(
                trip_id=payload.trip_id,
                route_id=payload.route_id,
                stop_id=payload.stop_id,
                scheduled_time=payload.scheduled_time,
                expected_time=payload.expected_time,
                status=payload.status,
                route_short_name=payload.route_short_name,
                route_mode=payload.route_mode,
                wheelchair_accessible=payload.wheelchair_accessible,
            )
        )

    return ValidationResult(valid=valid, quarantined=quarantined)
