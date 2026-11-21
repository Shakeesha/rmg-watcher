"""Tests for live fetching, retry behavior, and raw payload storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from transit_pipeline.config import Settings
from transit_pipeline.domain.exceptions import ApiError
from transit_pipeline.ingestion.fetcher import LiveTransitClient, create_fetcher
from transit_pipeline.ingestion.raw_store import RawStore
from transit_pipeline.ingestion.retries import RetryPolicy, request_with_retries


def test_factory_builds_live_client_outside_mock_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("TRANSIT_API_KEY", "secret")
    settings = Settings(mock_mode=False, _env_file=None)

    fetcher = create_fetcher(settings)

    assert isinstance(fetcher, LiveTransitClient)
    fetcher.close()


def test_live_client_fetches_departures_and_sends_api_key() -> None:
    with respx.mock:
        route = respx.get("https://api.example/departures/luisenplatz").mock(
            return_value=httpx.Response(200, json=[{"tripId": "trip-1"}])
        )
        with LiveTransitClient("https://api.example", api_key="secret") as client:
            payload = client.fetch_departures("luisenplatz")

        assert payload == [{"tripId": "trip-1"}]
        assert route.called
        assert route.calls[0].request.headers["X-Api-Key"] == "secret"


def test_live_client_accepts_wrapped_collections() -> None:
    with respx.mock:
        respx.get("https://api.example/stops").mock(
            return_value=httpx.Response(200, json={"stops": [{"stopId": "hbf"}]})
        )
        with LiveTransitClient("https://api.example") as client:
            assert client.fetch_stops() == [{"stopId": "hbf"}]


def test_transient_status_is_retried() -> None:
    with respx.mock:
        route = respx.get("https://api.example/departures/hbf").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=[{"tripId": "trip-2"}]),
            ]
        )
        with LiveTransitClient("https://api.example", sleep=lambda _: None) as client:
            assert client.fetch_departures("hbf") == [{"tripId": "trip-2"}]

        assert route.call_count == 2


def test_retries_stop_after_max_attempts() -> None:
    policy = RetryPolicy(max_attempts=2, base_delay=0.0)
    with respx.mock:
        route = respx.get("https://api.example/departures/hbf").mock(
            return_value=httpx.Response(503)
        )
        with LiveTransitClient(
            "https://api.example",
            retry_policy=policy,
            sleep=lambda _: None,
        ) as client, pytest.raises(ApiError):
            client.fetch_departures("hbf")

        assert route.call_count == 2


def test_client_errors_are_not_retried() -> None:
    with respx.mock:
        route = respx.get("https://api.example/departures/hbf").mock(
            return_value=httpx.Response(404)
        )
        with LiveTransitClient(
            "https://api.example", sleep=lambda _: None
        ) as client, pytest.raises(ApiError):
            client.fetch_departures("hbf")

        assert route.call_count == 1


def test_retry_after_header_is_honoured() -> None:
    delays: list[float] = []
    with respx.mock:
        respx.get("https://api.example/departures/hbf").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "2.5"}),
                httpx.Response(200, json=[]),
            ]
        )
        with httpx.Client() as client:
            response = request_with_retries(
                client,
                "https://api.example/departures/hbf",
                policy=RetryPolicy(max_attempts=2),
                sleep=delays.append,
            )

    assert response.status_code == 200
    assert delays == [2.5]


def test_raw_store_writes_metadata_and_payload(tmp_path: Path) -> None:
    store = RawStore(tmp_path / "raw")
    fetched_at = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)

    path = store.write_batch(
        [{"tripId": "trip-1"}],
        source="departures",
        batch_id="batch-1",
        fetched_at=fetched_at,
    )

    assert path == tmp_path / "raw" / "2026-11-21" / "batch-1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["batch_id"] == "batch-1"
    assert document["source"] == "departures"
    assert document["record_count"] == 1
    assert document["payload"] == [{"tripId": "trip-1"}]


def test_raw_store_overwrites_the_same_batch(tmp_path: Path) -> None:
    store = RawStore(tmp_path / "raw")
    fetched_at = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)

    first = store.write_batch(
        [{"tripId": "trip-1"}],
        source="departures",
        batch_id="b1",
        fetched_at=fetched_at,
    )
    second = store.write_batch(
        [{"tripId": "trip-2"}],
        source="departures",
        batch_id="b1",
        fetched_at=fetched_at,
    )

    assert first == second
    document = json.loads(second.read_text(encoding="utf-8"))
    assert document["payload"] == [{"tripId": "trip-2"}]
