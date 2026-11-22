<script lang="ts">
  import type { Departure } from '../lib/types'
  import { MILLISECONDS_PER_MINUTE, SECONDS_PER_MINUTE } from '../lib/constants'
  import {
    formatClockTime,
    transportIcon,
    transportLabel,
  } from '../lib/format'

  interface Props {
    departures: Departure[]
    loading: boolean
    stopName: string
    arriveBy: boolean
    onToggleArriveBy: (value: boolean) => void
  }

  let { departures, loading, stopName, arriveBy, onToggleArriveBy }: Props = $props()

  let accessibleOnly = $state(false)

  const visible = $derived(
    accessibleOnly
      ? departures.filter((departure) => departure.wheelchair_accessible === true)
      : departures,
  )

  function delayText(departure: Departure): string {
    if (departure.status === 'cancelled') return 'Cancelled'
    if (departure.delay_seconds === null) return 'No estimate'
    if (Math.abs(departure.delay_seconds) <= SECONDS_PER_MINUTE) return 'On time'
    const minutes = Math.round(
      Math.abs(departure.delay_seconds) / SECONDS_PER_MINUTE,
    )
    return `${departure.delay_seconds > 0 ? '+' : '−'}${minutes} min`
  }

  function relativeText(departure: Departure): string {
    if (departure.status === 'cancelled') return 'Cancelled'
    const target = new Date(departure.expected_time ?? departure.scheduled_time)
    if (Number.isNaN(target.getTime())) return '—'
    const minutes = Math.ceil((target.getTime() - Date.now()) / MILLISECONDS_PER_MINUTE)
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
      <div class="tabs" role="group" aria-label="Departures or arrivals">
        <button
          type="button"
          class:active={!arriveBy}
          data-nav
          onclick={() => onToggleArriveBy(false)}
        >
          Departures
        </button>
        <button
          type="button"
          class:active={arriveBy}
          data-nav
          onclick={() => onToggleArriveBy(true)}
        >
          Arrivals
        </button>
      </div>
    </div>
    <div class="header-actions">
      <button
        type="button"
        class="accessible-toggle"
        class:active={accessibleOnly}
        data-nav
        aria-pressed={accessibleOnly}
        title="Show only accessible departures"
        onclick={() => (accessibleOnly = !accessibleOnly)}
      >
        ♿
      </button>
      <span class="count">{visible.length} shown</span>
    </div>
  </header>

  {#if loading && visible.length === 0}
    <p class="state" role="status">Loading departures…</p>
  {:else if visible.length === 0}
    <p class="state" role="status">
      No upcoming {arriveBy ? 'arrivals' : 'departures'} for {stopName}.
    </p>
  {:else}
    <ol class="rows">
      {#each visible as departure (departure.trip_id)}
        <li class="departure-row" class:cancelled={departure.status === 'cancelled'}>
          <span
            class="mode-icon"
            role="img"
            aria-label={transportLabel(departure.mode)}
            title={transportLabel(departure.mode)}
          >
            {transportIcon(departure.mode)}
          </span>

          <span class="route-badge" aria-label={`Route ${departure.route_short_name}`}>
            {departure.route_short_name}
          </span>

          <span class="departure-main">
            <span class="departure-time">
              {formatClockTime(departure.expected_time ?? departure.scheduled_time)}
            </span>
            <span class="departure-sub">
              {#if departure.wheelchair_accessible}
                ♿
              {/if}
              {#if departure.expected_time}
                scheduled {formatClockTime(departure.scheduled_time)}
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

  .tabs {
    display: flex;
    gap: 8px;
    margin-top: 6px;
  }

  .tabs button {
    min-height: 44px;
    padding: 0 14px;
    border: 1px solid #2d3a49;
    border-radius: 999px;
    background: #18212b;
    color: var(--color-muted);
    font-size: 0.85rem;
    font-weight: 700;
    cursor: pointer;
  }

  .tabs button.active {
    border-color: var(--color-accent);
    background: #123d25;
    color: #d9ffe7;
  }

  .header-actions {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 10px;
  }

  .accessible-toggle {
    min-width: 52px;
    min-height: 44px;
    border: 1px solid #2d3a49;
    border-radius: 10px;
    background: #18212b;
    color: var(--color-text);
    font-size: 1.1rem;
    cursor: pointer;
  }

  .accessible-toggle.active {
    border-color: #7dd3fc;
    background: #123247;
    color: #e0f5ff;
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
    grid-template-columns: 30px 64px minmax(0, 1fr) auto auto;
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

  .mode-icon {
    display: grid;
    place-items: center;
    font-size: 1.5rem;
    line-height: 1;
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
      grid-template-columns: 26px 56px minmax(0, 1fr) auto;
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
