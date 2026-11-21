<script lang="ts">
  import type { Departure } from '../lib/types'

  interface Props {
    departures: Departure[]
    loading: boolean
    stopName: string
  }

  let { departures, loading, stopName }: Props = $props()

  const timeFormatter = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  function formatTime(value: string | null): string {
    if (value === null) return '—'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '—'
    return timeFormatter.format(date)
  }

  function delayText(departure: Departure): string {
    if (departure.status === 'cancelled') return 'Cancelled'
    if (departure.delay_seconds === null) return 'No estimate'
    if (Math.abs(departure.delay_seconds) <= 60) return 'On time'
    const minutes = Math.round(Math.abs(departure.delay_seconds) / 60)
    return `${departure.delay_seconds > 0 ? '+' : '−'}${minutes} min`
  }

  function relativeText(departure: Departure): string {
    if (departure.status === 'cancelled') return 'Cancelled'
    const target = new Date(departure.expected_time ?? departure.scheduled_time)
    if (Number.isNaN(target.getTime())) return '—'
    const minutes = Math.ceil((target.getTime() - Date.now()) / 60_000)
    if (minutes <= 0) return 'Due'
    return `in ${minutes} min`
  }

  function categoryClass(departure: Departure): string {
    return departure.status === 'cancelled' ? 'cancelled' : departure.delay_category
  }
</script>

<section class="departure-list" aria-label="Departures" aria-busy={loading}>
  <header class="list-header">
    <div>
      <h2>{stopName}</h2>
      <p>Next departures</p>
    </div>
    <span class="count">{departures.length} shown</span>
  </header>

  {#if loading && departures.length === 0}
    <p class="state" role="status">Loading departures…</p>
  {:else if departures.length === 0}
    <p class="state" role="status">No upcoming departures for {stopName}.</p>
  {:else}
    <ol class="rows">
      {#each departures as departure (departure.trip_id)}
        <li class="departure-row" class:cancelled={departure.status === 'cancelled'}>
          <span class="route-badge" aria-label={`Route ${departure.route_short_name}`}>
            {departure.route_short_name}
          </span>

          <span class="departure-main">
            <span class="departure-time">
              {formatTime(departure.expected_time ?? departure.scheduled_time)}
            </span>
            <span class="departure-sub">
              {#if departure.expected_time}
                scheduled {formatTime(departure.scheduled_time)}
              {:else}
                scheduled
              {/if}
            </span>
          </span>

          <span class="countdown">{relativeText(departure)}</span>

          <span class={`delay-badge ${categoryClass(departure)}`}>
            {delayText(departure)}
          </span>
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .departure-list {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
  }

  .list-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
    padding: 2px 4px 10px;
  }

  h2 {
    margin: 0;
    font-size: 1.35rem;
    line-height: 1.15;
  }

  .list-header p {
    margin: 2px 0 0;
    color: var(--color-muted);
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .count {
    flex: 0 0 auto;
    color: var(--color-muted);
    font-size: 0.78rem;
    font-variant-numeric: tabular-nums;
  }

  .rows {
    display: grid;
    gap: 6px;
    min-height: 0;
    margin: 0;
    padding: 0 0 8px;
    overflow-y: auto;
    list-style: none;
  }

  .departure-row {
    display: grid;
    grid-template-columns: 64px minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 14px;
    min-height: 66px;
    padding: 6px 12px 6px 8px;
    border: 1px solid #263241;
    border-left: 4px solid var(--color-accent);
    border-radius: 10px;
    background: var(--color-surface);
  }

  .departure-row.cancelled {
    border-left-color: var(--color-danger);
    opacity: 0.82;
  }

  .route-badge {
    display: grid;
    place-items: center;
    width: 56px;
    height: 52px;
    border-radius: 8px;
    background: #e8edf2;
    color: #0b0f14;
    font-size: 1.45rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }

  .departure-main {
    display: flex;
    min-width: 0;
    flex-direction: column;
  }

  .departure-time {
    font-size: 1.55rem;
    font-weight: 750;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.01em;
    line-height: 1.05;
  }

  .departure-sub {
    overflow: hidden;
    color: var(--color-muted);
    font-size: 0.78rem;
    font-variant-numeric: tabular-nums;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .countdown {
    color: var(--color-muted);
    font-size: 0.86rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .delay-badge {
    min-width: 94px;
    padding: 7px 10px;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 800;
    text-align: center;
    white-space: nowrap;
  }

  .delay-badge.on_time {
    background: #123d25;
    color: #b9f6ce;
  }

  .delay-badge.minor {
    background: #3c310f;
    color: #ffd98b;
  }

  .delay-badge.major {
    background: #4a240e;
    color: #ffc18f;
  }

  .delay-badge.severe {
    background: #4b1616;
    color: #ffb4b4;
  }

  .delay-badge.cancelled {
    background: #4b1616;
    color: #ffb4b4;
  }

  .delay-badge.unknown {
    background: #263241;
    color: var(--color-muted);
  }

  .state {
    margin: 8px 0;
    padding: 22px 16px;
    border: 1px dashed #2d3a49;
    border-radius: 10px;
    color: var(--color-muted);
    text-align: center;
  }

  @media (max-width: 560px) {
    .departure-row {
      grid-template-columns: 56px minmax(0, 1fr) auto;
      gap: 10px;
    }

    .countdown {
      display: none;
    }

    .delay-badge {
      min-width: 82px;
    }
  }
</style>
