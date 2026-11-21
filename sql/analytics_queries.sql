-- Analytical queries used for health checks and dashboards.

-- Punctuality and mean delay by stop.
SELECT
    stop_id,
    COUNT(*) AS event_count,
    ROUND(
        AVG(CASE WHEN delay_seconds IS NOT NULL AND delay_seconds <= 300 THEN 1.0 ELSE 0.0 END),
        3
    ) AS punctuality_rate,
    ROUND(AVG(delay_seconds), 1) AS mean_delay_seconds
FROM fact_stop_events
GROUP BY stop_id
ORDER BY punctuality_rate ASC;

-- Top delayed routes by worst observed delay.
SELECT
    route_id,
    MAX(delay_seconds) AS max_delay_seconds,
    COUNT(*) AS event_count
FROM fact_stop_events
WHERE delay_seconds IS NOT NULL
GROUP BY route_id
ORDER BY max_delay_seconds DESC
LIMIT 5;

-- Recent pipeline runs and reconciliation counters.
SELECT
    run_id,
    started_at,
    finished_at,
    status,
    raw_count,
    valid_count,
    deduplicated_count,
    loaded_count,
    quarantined_count
FROM pipeline_runs
ORDER BY started_at DESC
LIMIT 10;
