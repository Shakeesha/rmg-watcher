<script lang="ts">
  import type { Connection, Stop } from '../lib/types'

  interface Props {
    stops: Stop[]
    selectedStopId: string | null
    connections: Connection[]
    loading: boolean
    error: string | null
    onSearch: (from: string, to: string) => void
  }

  let {
    stops,
    selectedStopId,
    connections,
    loading,
    error,
    onSearch,
  }: Props = $props()

  let fromStop = $state('')
  let toStop = $state('')

  $effect(() => {
    if (selectedStopId && !fromStop) fromStop = selectedStopId
  })

  const timeFormatter = new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  function formatTime(value: string): string {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '—'
    return timeFormatter.format(date)
  }

  function routeLabel(route: string | null, mode: string): string {
    if (!route) return mode === 'walk' ? 'Walk' : mode.toUpperCase()
    if (!route.includes(':')) return route
    return route.split(':').at(-1)?.replace(/^_+/, '') || mode.toUpperCase()
  }

  function canSearch(): boolean {
    return fromStop !== '' && toStop !== '' && fromStop !== toStop
  }
</script>

<section class="connections" aria-label="Connections" aria-busy={loading}>
  <header class="connections-header">
    <div>
      <h2>Connections</h2>
      <p>Plan a trip between two stops</p>
    </div>
    {#if connections.length > 0}
      <span class="count">{connections.length} found</span>
    {/if}
  </header>

  <div class="search-row">
    <label>
      <span>From</span>
      <select bind:value={fromStop} data-nav>
        <option value="">Select a stop</option>
        {#each stops as stop (stop.stop_id)}
          <option value={stop.stop_id}>{stop.name}</option>
        {/each}
      </select>
    </label>

    <label>
      <span>To</span>
      <select bind:value={toStop} data-nav>
        <option value="">Select a stop</option>
        {#each stops as stop (stop.stop_id)}
          <option value={stop.stop_id}>{stop.name}</option>
        {/each}
      </select>
    </label>

    <button
      type="button"
      class="search-button"
      data-nav
      disabled={!canSearch() || loading}
      onclick={() => onSearch(fromStop, toStop)}
    >
      {loading ? 'Searching…' : 'Search'}
    </button>
  </div>

  {#if error}
    <p class="state error" role="status">{error}</p>
  {:else if loading}
    <p class="state" role="status">Planning connections…</p>
  {:else if connections.length === 0}
    <p class="state" role="status">Choose two stops to find a connection.</p>
  {:else}
    <ol class="connection-list">
      {#each connections as connection, index (index)}
        <li class="connection-row">
          <div class="connection-summary">
            <strong>
              {formatTime(connection.departure)} → {formatTime(connection.arrival)}
            </strong>
            <span>
              {connection.duration_minutes} min ·
              {connection.transfers === 0 ? 'direct' : `${connection.transfers} changes`}
            </span>
          </div>

          <div class="legs">
            {#each connection.legs as leg, legIndex (legIndex)}
              <span class="leg">
                <span class="route-chip">{routeLabel(leg.route, leg.mode)}</span>
                <span class="leg-stops">
                  {leg.from_name} → {leg.to_name}
                </span>
                <span class="leg-time">
                  {formatTime(leg.departure)}–{formatTime(leg.arrival)}
                </span>
              </span>
            {/each}
          </div>
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .connections {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    min-height: 0;
    overflow-y: auto;
  }

  .connections-header {
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

  .connections-header p {
    margin: 2px 0 0;
    color: var(--color-muted);
    font-size: 0.82rem;
  }

  .count {
    color: var(--color-muted);
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }

  .search-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
    align-items: end;
    gap: 10px;
  }

  label {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 4px;
  }

  label span {
    color: var(--color-muted);
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  select {
    width: 100%;
    min-height: 54px;
    padding: 0 10px;
    border: 1px solid #2d3a49;
    border-radius: 10px;
    background: var(--color-surface);
    color: var(--color-text);
    font: inherit;
  }

  .search-button {
    min-width: 120px;
    min-height: 54px;
    padding: 0 18px;
    border: 1px solid var(--color-accent);
    border-radius: 10px;
    background: #123d25;
    color: #d9ffe7;
    font-weight: 800;
    cursor: pointer;
  }

  .search-button:disabled {
    border-color: #2d3a49;
    background: #18212b;
    color: var(--color-muted);
    cursor: default;
  }

  .connection-list {
    display: grid;
    gap: 8px;
    margin: 0;
    padding: 0 0 8px;
    list-style: none;
  }

  .connection-row {
    padding: 12px;
    border: 1px solid #263241;
    border-left: 4px solid var(--color-accent);
    border-radius: 10px;
    background: var(--color-surface);
  }

  .connection-summary {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }

  .connection-summary strong {
    font-size: 1.1rem;
    font-variant-numeric: tabular-nums;
  }

  .connection-summary span {
    color: var(--color-muted);
    font-size: 0.84rem;
  }

  .legs {
    display: grid;
    gap: 6px;
  }

  .leg {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .route-chip {
    display: grid;
    place-items: center;
    min-width: 44px;
    height: 34px;
    padding: 0 8px;
    border-radius: 6px;
    background: #e8edf2;
    color: #0b0f14;
    font-size: 0.85rem;
    font-weight: 800;
  }

  .leg-stops {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .leg-time {
    margin-left: auto;
    color: var(--color-muted);
    font-size: 0.78rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .state {
    margin: 8px 0;
    padding: 22px 16px;
    border: 1px dashed #2d3a49;
    border-radius: 10px;
    color: var(--color-muted);
    text-align: center;
  }

  .state.error {
    border-color: #4b1616;
    color: #ffb4b4;
  }

  @media (max-width: 600px) {
    .search-row {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    }

    .search-button {
      grid-column: 1 / -1;
    }
  }
</style>
