<script lang="ts">
  import type { Connection, FavouriteConnection, Stop } from '../lib/types'

  interface Props {
    stops: Stop[]
    selectedStopId: string | null
    connections: Connection[]
    loading: boolean
    error: string | null
    favourites: FavouriteConnection[]
    onSearch: (from: string, to: string, time?: string, arriveBy?: boolean) => void
    onSave: (from: string, to: string, label: string) => void
    onSelectFavourite: (favourite: FavouriteConnection) => void
  }

  let {
    stops,
    selectedStopId,
    connections,
    loading,
    error,
    favourites,
    onSearch,
    onSave,
    onSelectFavourite,
  }: Props = $props()

  let fromStop = $state('')
  let toStop = $state('')
  let travelTime = $state('')
  let arriveBy = $state(false)

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

  function stopName(stopId: string): string {
    return stops.find((stop) => stop.stop_id === stopId)?.name ?? stopId
  }

  function routeLabel(route: string | null, mode: string): string {
    if (!route) return mode === 'walk' ? 'Walk' : mode.toUpperCase()
    if (!route.includes(':')) return route
    return route.split(':').at(-1)?.replace(/^_+/, '') || mode.toUpperCase()
  }

  function canSearch(): boolean {
    return fromStop !== '' && toStop !== '' && fromStop !== toStop
  }

  function swapStops(): void {
    const previous = fromStop
    fromStop = toStop
    toStop = previous
  }

  function toLocalInput(date: Date): string {
    const pad = (value: number) => String(value).padStart(2, '0')
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
  }

  function setOffset(minutes: number): void {
    travelTime = toLocalInput(new Date(Date.now() + minutes * 60_000))
  }

  function shiftTime(minutes: number): void {
    const base = travelTime ? new Date(travelTime) : new Date()
    travelTime = toLocalInput(new Date(base.getTime() + minutes * 60_000))
  }

  function search(): void {
    if (!canSearch()) return
    onSearch(fromStop, toStop, travelTime || undefined, arriveBy)
  }

  function save(): void {
    if (!canSearch()) return
    onSave(fromStop, toStop, `${stopName(fromStop)} → ${stopName(toStop)}`)
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

    <label>
      <span>Date & time</span>
      <input type="datetime-local" bind:value={travelTime} data-nav />
    </label>
  </div>

  <div class="action-row">
    <button type="button" class="swap-button" data-nav onclick={swapStops} aria-label="Swap from and to stops">
      ⇅
    </button>

    <div class="time-mode" role="group" aria-label="Time mode">
      <button
        type="button"
        class:active={!arriveBy}
        data-nav
        onclick={() => (arriveBy = false)}
      >
        Depart at
      </button>
      <button
        type="button"
        class:active={arriveBy}
        data-nav
        onclick={() => (arriveBy = true)}
      >
        Arrive by
      </button>
    </div>

    <button
      type="button"
      class="search-button"
      data-nav
      disabled={!canSearch() || loading}
      onclick={search}
    >
      {loading ? 'Searching…' : 'Search'}
    </button>

    <button
      type="button"
      class="save-button"
      data-nav
      disabled={!canSearch()}
      onclick={save}
    >
      Save
    </button>
  </div>

  <div class="quick-times" role="group" aria-label="Quick time selection">
    <button type="button" data-nav onclick={() => setOffset(0)}>Now</button>
    <button type="button" data-nav onclick={() => setOffset(15)}>in 15 min</button>
    <button type="button" data-nav onclick={() => setOffset(60)}>in 1 h</button>
    <button type="button" data-nav onclick={() => shiftTime(-15)}>Earlier</button>
    <button type="button" data-nav onclick={() => shiftTime(15)}>Later</button>
  </div>

  {#if favourites.length > 0}
    <div class="favourites" role="group" aria-label="Favourite connections">
      {#each favourites as favourite (favourite.from + favourite.to)}
        <button
          type="button"
          class="favourite"
          data-nav
          onclick={() => {
            fromStop = favourite.from
            toStop = favourite.to
            onSelectFavourite(favourite)
          }}
        >
          ★ {favourite.label}
        </button>
      {/each}
    </div>
  {/if}

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
    gap: 10px;
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
  }

  .search-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.1fr);
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

  select,
  input {
    width: 100%;
    min-height: 54px;
    padding: 0 10px;
    border: 1px solid #2d3a49;
    border-radius: 10px;
    background: var(--color-surface);
    color: var(--color-text);
    font: inherit;
  }

  .action-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .swap-button {
    flex: 0 0 auto;
    min-width: 54px;
    min-height: 54px;
    border: 1px solid #2d3a49;
    border-radius: 10px;
    background: #18212b;
    color: #bde9ff;
    font-size: 1.4rem;
    font-weight: 800;
    cursor: pointer;
  }

  .quick-times {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .quick-times button {
    min-height: 44px;
    padding: 0 12px;
    border: 1px solid #2d3a49;
    border-radius: 999px;
    background: #18212b;
    color: var(--color-text);
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
  }

  .time-mode {
    display: flex;
    gap: 6px;
  }

  .time-mode button,
  .search-button,
  .save-button {
    min-height: 54px;
    padding: 0 16px;
    border: 1px solid #2d3a49;
    border-radius: 10px;
    background: #18212b;
    color: var(--color-text);
    font-weight: 700;
    cursor: pointer;
  }

  .time-mode button.active {
    border-color: var(--color-accent);
    background: #123d25;
    color: #d9ffe7;
  }

  .search-button {
    margin-left: auto;
    border-color: var(--color-accent);
    background: #123d25;
    color: #d9ffe7;
  }

  .save-button {
    border-color: #7dd3fc;
    color: #bde9ff;
  }

  .search-button:disabled,
  .save-button:disabled {
    border-color: #2d3a49;
    color: var(--color-muted);
    cursor: default;
  }

  .favourites {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .favourite {
    min-height: 44px;
    padding: 0 12px;
    border: 1px solid #4a3410;
    border-radius: 999px;
    background: #2a1f0d;
    color: #ffd58a;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
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

    .search-row label:last-child {
      grid-column: 1 / -1;
    }
  }
</style>
