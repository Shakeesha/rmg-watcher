<script lang="ts">
  import type { Metrics } from '../lib/types'

  interface Props {
    metrics: Metrics | null
    loading: boolean
  }

  let { metrics, loading }: Props = $props()

  const punctualityPercent = $derived(
    metrics === null ? null : Math.round(metrics.punctuality_rate * 100),
  )

  const punctualityTone = $derived.by(() => {
    if (metrics === null) return 'neutral'
    if (metrics.punctuality_rate >= 0.8) return 'good'
    if (metrics.punctuality_rate >= 0.6) return 'warning'
    return 'danger'
  })

  function formatDuration(seconds: number | null | undefined): string {
    if (seconds === null || seconds === undefined) return '—'
    const rounded = Math.round(seconds)
    if (rounded < 60) return `${rounded}s`
    const minutes = Math.floor(rounded / 60)
    const rest = rounded % 60
    return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`
  }

  function routeLabel(routeId: string): string {
    return routeId.replace(/^route[-_]?/i, '') || routeId
  }
</script>

<section class="delay-metrics-card" aria-label="Delay metrics" aria-busy={loading}>
  <header class="card-header">
    <div>
      <h2>Delay stats</h2>
      <p>Recent departures across all stops</p>
    </div>
    <span class="event-count">
      {metrics === null ? '—' : metrics.total_events} events
    </span>
  </header>

  {#if loading && metrics === null}
    <p class="state" role="status">Loading delay metrics…</p>
  {:else if metrics === null || metrics.total_events === 0}
    <p class="state" role="status">No delay data recorded yet.</p>
  {:else}
    <div class="tiles">
      <article class={`metric-tile ${punctualityTone}`}>
        <span class="metric-label">Punctuality</span>
        <strong>{punctualityPercent}%</strong>
        <span class="metric-note">within 5 min of schedule</span>
      </article>

      <article class="metric-tile">
        <span class="metric-label">Median delay</span>
        <strong>{formatDuration(metrics.median_delay_seconds)}</strong>
        <span class="metric-note">typical departure</span>
      </article>

      <article class="metric-tile">
        <span class="metric-label">95th percentile</span>
        <strong>{formatDuration(metrics.p95_delay_seconds)}</strong>
        <span class="metric-note">slowest 5% of departures</span>
      </article>
    </div>

    <section class="top-routes" aria-label="Top delayed lines">
      <h3>Top delayed lines</h3>
      <ol>
        {#each metrics.top_delayed_routes as route (route.route_id)}
          <li>
            <span class="route-chip">{route.route_short_name ?? routeLabel(route.route_id)}</span>
            <span class="route-id">{route.route_id}</span>
            <span class="route-delay">{formatDuration(route.max_delay_seconds)}</span>
          </li>
        {:else}
          <li class="empty">No delayed lines recorded.</li>
        {/each}
      </ol>
    </section>
  {/if}
</section>

<style>
  .delay-metrics-card {
    display: flex;
    flex-direction: column;
    gap: 14px;
    height: 100%;
    min-height: 0;
    overflow-y: auto;
  }

  .card-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
    padding: 2px 4px 0;
  }

  h2 {
    margin: 0;
    font-size: 1.35rem;
    line-height: 1.15;
  }

  .card-header p {
    margin: 2px 0 0;
    color: var(--color-muted);
    font-size: 0.82rem;
  }

  .event-count {
    flex: 0 0 auto;
    color: var(--color-muted);
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }

  .tiles {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .metric-tile {
    display: flex;
    min-height: 118px;
    flex-direction: column;
    justify-content: center;
    padding: 14px;
    border: 1px solid #263241;
    border-top: 4px solid #3c4b5c;
    border-radius: 12px;
    background: var(--color-surface);
  }

  .metric-tile.good {
    border-top-color: var(--color-accent);
  }

  .metric-tile.warning {
    border-top-color: var(--color-warning);
  }

  .metric-tile.danger {
    border-top-color: var(--color-danger);
  }

  .metric-label {
    color: var(--color-muted);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .metric-tile strong {
    margin: 2px 0 0;
    font-size: clamp(1.8rem, 5vw, 2.5rem);
    font-variant-numeric: tabular-nums;
    line-height: 1.05;
  }

  .metric-note {
    margin-top: 4px;
    color: var(--color-muted);
    font-size: 0.74rem;
  }

  .top-routes {
    padding: 12px;
    border: 1px solid #263241;
    border-radius: 12px;
    background: #10161d;
  }

  .top-routes h3 {
    margin: 0 0 8px;
    color: var(--color-muted);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .top-routes ol {
    display: grid;
    gap: 6px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .top-routes li {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 40px;
    padding: 4px 8px;
    border-radius: 8px;
    background: var(--color-surface);
  }

  .route-chip {
    display: grid;
    place-items: center;
    min-width: 38px;
    height: 32px;
    padding: 0 7px;
    border-radius: 6px;
    background: #e8edf2;
    color: #0b0f14;
    font-weight: 800;
  }

  .route-id {
    min-width: 0;
    overflow: hidden;
    color: var(--color-muted);
    font-size: 0.8rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .route-delay {
    margin-left: auto;
    color: #ffc18f;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }

  .empty {
    color: var(--color-muted);
    font-size: 0.85rem;
  }

  .state {
    margin: 8px 0;
    padding: 22px 16px;
    border: 1px dashed #2d3a49;
    border-radius: 10px;
    color: var(--color-muted);
    text-align: center;
  }

  @media (max-width: 600px) {
    .tiles {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .metric-tile:first-child {
      grid-column: 1 / -1;
      min-height: 92px;
    }
  }
</style>
