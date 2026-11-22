"""Persistence of unmodified raw API payloads with batch metadata."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from rmg_watcher.domain.exceptions import StorageError


class RawStore:
    """Writes immutable raw payload snapshots grouped by date and batch."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def write_batch(
        self,
        payload: Sequence[Mapping[str, Any]],
        *,
        source: str,
        batch_id: str | None = None,
        fetched_at: datetime | None = None,
    ) -> Path:
        """Persist a payload atomically and return the written path."""
        batch = batch_id or uuid4().hex
        timestamp = fetched_at or datetime.now(UTC)
        directory = self.root / timestamp.strftime("%Y-%m-%d")
        path = directory / f"{batch}.json"
        document = {
            "batch_id": batch,
            "source": source,
            "fetched_at": timestamp.isoformat(),
            "record_count": len(payload),
            "payload": list(payload),
        }

        try:
            directory.mkdir(parents=True, exist_ok=True)
            temporary_path = path.with_suffix(".json.tmp")
            temporary_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary_path, path)
        except OSError as exc:
            raise StorageError(f"Could not write raw batch {path}: {exc}") from exc

        return path
