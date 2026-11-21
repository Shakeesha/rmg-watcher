"""Shared pytest fixtures, forced mock client, and outbound network blocker."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from transit_pipeline.config import Settings
from transit_pipeline.ingestion.fetcher import MockTransitClient


@pytest.fixture(autouse=True)
def block_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail fast if a test accidentally opens a remote socket."""
    original_connect = socket.socket.connect

    def guarded_connect(sock: socket.socket, address: Any) -> None:
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError(f"Outbound network access blocked: {host}")
        original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings isolated to a temporary directory and forced into mock mode."""
    return Settings(
        mock_mode=True,
        database_path=tmp_path / "transit.db",
        raw_store_path=tmp_path / "raw",
        quarantine_path=tmp_path / "quarantine",
        frontend_dist_path=tmp_path / "dist",
        _env_file=None,
    )


@pytest.fixture
def mock_fetcher() -> MockTransitClient:
    """Mock client backed by the repository fixtures."""
    return MockTransitClient()
