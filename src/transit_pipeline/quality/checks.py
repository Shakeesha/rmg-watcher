"""Post-run data quality gates: null checks and row count reconciliation."""

from __future__ import annotations

from dataclasses import dataclass

from transit_pipeline.storage.repository import TransitRepository


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Result of the post-run data quality gates."""

    ok: bool
    errors: list[str]
    raw_count: int
    valid_count: int
    deduplicated_count: int
    loaded_count: int
    quarantined_count: int


def run_quality_checks(
    *,
    raw_count: int,
    valid_count: int,
    deduplicated_count: int,
    loaded_count: int,
    quarantined_count: int,
    repository: TransitRepository,
) -> QualityReport:
    """Reconcile counts and verify fact-table integrity."""
    errors: list[str] = []

    if valid_count + quarantined_count != raw_count:
        errors.append(
            "raw count mismatch: "
            f"{raw_count} raw != {valid_count} valid + {quarantined_count} quarantined"
        )

    if loaded_count + deduplicated_count != valid_count:
        errors.append(
            "valid count mismatch: "
            f"{valid_count} valid != {loaded_count} loaded + {deduplicated_count} duplicates"
        )

    null_violations = repository.count_null_violations()
    if null_violations:
        errors.append(f"{null_violations} fact rows contain empty required values")

    foreign_key_violations = repository.foreign_key_violations()
    if foreign_key_violations:
        errors.append(f"{foreign_key_violations} foreign key violations found")

    return QualityReport(
        ok=not errors,
        errors=errors,
        raw_count=raw_count,
        valid_count=valid_count,
        deduplicated_count=deduplicated_count,
        loaded_count=loaded_count,
        quarantined_count=quarantined_count,
    )
