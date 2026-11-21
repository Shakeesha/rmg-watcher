# Schema

SQLite stores a small star schema; `sql/schema.sql` is the source of truth.

## Tables

| Table | Purpose |
| --- | --- |
| `dim_stops` | Stop metadata (`stop_id`, name, coordinates). |
| `dim_routes` | Route metadata (`route_id`, short/long name, mode). |
| `fact_stop_events` | One row per `(trip_id, stop_id)` with schedule, expected time, delay, and status. |
| `quarantine` | Rejected records with batch, hash, reason, and raw payload. |
| `pipeline_runs` | Per-run counters and status for health checks. |

## Constraints

- `fact_stop_events` is unique on `(trip_id, stop_id)`; repeated runs upsert in place.
- Composite indexes cover stop/time, route/time, and observed-at lookups.
- Foreign keys link facts to `dim_stops` and `dim_routes`.

## Metrics

- **Delay seconds:** `expected_time - scheduled_time`.
- **Categories:** on time `<= 60 s`, minor `61–300 s`, major `301–900 s`, severe `> 900 s`, cancelled.
- **Punctuality:** share of events at or below the 300-second threshold.
- **Percentiles:** median and 95th percentile of non-null delay seconds.

## Quarantine

Validation failures never reach the fact table. Each rejected record is stored
with the originating batch, a SHA-256 payload hash, a human-readable reason, and
the original JSON so it can be inspected or replayed.
