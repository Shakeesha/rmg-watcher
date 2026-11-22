<script lang="ts">
  import { fetchPlaces, resolvePlace } from '../lib/api'
  import {
    AUTOCOMPLETE_DEBOUNCE_MS,
    FAVOURITE_LABEL_SEPARATOR,
    QUICK_OFFSET_FIFTEEN_MIN,
    QUICK_OFFSET_ONE_HOUR_MIN,
  } from '../lib/constants'
  import { formatTime, routeLabel } from '../lib/format'
  import type {
    Connection,
    FavouriteConnection,
    PlaceResult,
    ServiceAlert,
    Stop,
  } from '../lib/types'

  interface Props {
    stops: Stop[]
    selectedStopId: string | null
    connections: Connection[]
    loading: boolean
    error: string | null
    favourites: FavouriteConnection[]
    alerts: ServiceAlert[]
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
    alerts,
    onSearch,
    onSave,
    onSelectFavourite,
  }: Props = $props()

  let fromStop = $state('')
  let toStop = $state('')
  let travelTime = $state('')
  let arriveBy = $state(false)
  let expanded = $state<Record<string, boolean>>({})
  let selectedIndex = $state<number | null>(null)

  const selectedConnection = $derived(
    selectedIndex === null ? null : (connections[selectedIndex] ?? null),
  )

  $effect(() => {
    connections
    selectedIndex = null
  })

  let fromText = $state('')
  let toText = $state('')
  let fromSelectedText = $state('')
  let toSelectedText = $state('')
  let fromSuggestions = $state<PlaceResult[]>([])
  let toSuggestions = $state<PlaceResult[]>([])
  let fromLoading = $state(false)
  let toLoading = $state(false)
  let fromController: AbortController | null = null
  let toController: AbortController | null = null
  let resolving = $state(false)

  $effect(() => {
    const term = fromText.trim()
    if (term.length < 2 || term === fromSelectedText) {
      fromSuggestions = []
      return
    }
    const timer = window.setTimeout(async () => {
      fromController?.abort()
      const controller = new AbortController()
      fromController = controller
      fromLoading = true
      try {
        fromSuggestions = await fetchPlaces(term, controller.signal)
      } catch {
        fromSuggestions = []
      } finally {
        fromLoading = false
      }
    }, AUTOCOMPLETE_DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      fromController?.abort()
    }
  })

  $effect(() => {
    const term = toText.trim()
    if (term.length < 2 || term === toSelectedText) {
      toSuggestions = []
      return
    }
    const timer = window.setTimeout(async () => {
      toController?.abort()
      const controller = new AbortController()
      toController = controller
      toLoading = true
      try {
        toSuggestions = await fetchPlaces(term, controller.signal)
      } catch {
        toSuggestions = []
      } finally {
        toLoading = false
      }
    }, AUTOCOMPLETE_DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      toController?.abort()
    }
  })

  async function chooseFrom(place: PlaceResult): Promise<void> {
    fromSuggestions = []
    resolving = true
    let selected = place
    try {
      selected = (await resolvePlace(place.id)) ?? place
    } catch {
      selected = place
    } finally {
      resolving = false
    }
    fromStop = selected.id
    fromText = selected.name
    fromSelectedText = selected.name
  }

  async function chooseTo(place: PlaceResult): Promise<void> {
    toSuggestions = []
    resolving = true
    let selected = place
    try {
      selected = (await resolvePlace(place.id)) ?? place
    } catch {
      selected = place
    } finally {
      resolving = false
    }
    toStop = selected.id
    toText = selected.name
    toSelectedText = selected.name
  }

  $effect(() => {
    if (selectedStopId && !fromStop) {
      fromStop = selectedStopId
      const stop = stops.find((item) => item.stop_id === selectedStopId)
      if (stop) {
        fromText = stop.name
        fromSelectedText = stop.name
      }
    }
  })

  function canSearch(): boolean {
    return (
      !resolving && fromStop !== '' && toStop !== '' && fromStop !== toStop
    )
  }

  function swapStops(): void {
    const previousId = fromStop
    const previousText = fromText
    const previousSelected = fromSelectedText
    fromStop = toStop
    fromText = toText
    fromSelectedText = toSelectedText
    toStop = previousId
    toText = previousText
    toSelectedText = previousSelected
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

  function toggleDetails(key: string): void {
    expanded[key] = !expanded[key]
  }

  function routeStyle(color: string | null): string {
    if (!color) return ''
    const value = color.startsWith('#') ? color : `#${color}`
    return `background-color: ${value}`
  }

  function transitLegs(connection: Connection): Connection['legs'] {
    return connection.legs.filter((leg) => {
      const mode = leg.mode.toLowerCase()
      return !mode.includes('walk') && !mode.includes('foot')
    })
  }

  function tightTransferMinutes(connection: Connection): number[] {
    const result: number[] = []
    let previous: (typeof connection.legs)[number] | null = null

    for (const leg of connection.legs) {
      const mode = leg.mode.toLowerCase()
      if (mode.includes('walk') || mode.includes('foot')) continue

      if (previous !== null) {
        const arrival = new Date(previous.arrival).getTime()
        const departure = new Date(leg.departure).getTime()
        if (!Number.isNaN(arrival) && !Number.isNaN(departure)) {
          const minutes = Math.round((departure - arrival) / 60_000)
          if (minutes >= 0 && minutes <= 5) result.push(minutes)
        }
      }
      previous = leg
    }

    return result
  }

  function affectedAlert(connection: Connection): ServiceAlert | null {
    const ids = new Set(
      connection.legs
        .map((leg) => leg.route_id)
        .filter((id): id is string => id !== null),
    )
    return alerts.find((alert) => alert.routes.some((route) => ids.has(route))) ?? null
  }

  function search(): void {
    if (!canSearch()) return
    onSearch(fromStop, toStop, travelTime || undefined, arriveBy)
  }

  function save(): void {
    if (!canSearch()) return
    onSave(
      fromStop,
      toStop,
      `${fromSelectedText || fromStop}${FAVOURITE_LABEL_SEPARATOR}${toSelectedText || toStop}`,
    )
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
    <label class="place-field">
      <span>From</span>
      <input
        type="search"
        placeholder="Any stop in Germany"
        aria-label="From stop"
        bind:value={fromText}
        oninput={() => (fromSelectedText = '')}
        data-nav
      />
      {#if fromText.trim().length >= 2 && fromText !== fromSelectedText}
        <div class="suggestions" role="listbox" aria-label="From suggestions">
          {#if fromLoading}
            <p class="empty">Searching…</p>
          {:else if fromSuggestions.length === 0}
            <p class="empty">No stops found.</p>
          {:else}
            {#each fromSuggestions as place (place.id)}
              <button
                type="button"
                role="option"
                aria-selected={fromStop === place.id}
                data-nav
                onclick={() => chooseFrom(place)}
              >
                {place.name}
              </button>
            {/each}
          {/if}
        </div>
      {/if}
    </label>

    <label class="place-field">
      <span>To</span>
      <input
        type="search"
        placeholder="Any stop in Germany"
        aria-label="To stop"
        bind:value={toText}
        oninput={() => (toSelectedText = '')}
        data-nav
      />
      {#if toText.trim().length >= 2 && toText !== toSelectedText}
        <div class="suggestions" role="listbox" aria-label="To suggestions">
          {#if toLoading}
            <p class="empty">Searching…</p>
          {:else if toSuggestions.length === 0}
            <p class="empty">No stops found.</p>
          {:else}
            {#each toSuggestions as place (place.id)}
              <button
                type="button"
                role="option"
                aria-selected={toStop === place.id}
                data-nav
                onclick={() => chooseTo(place)}
              >
                {place.name}
              </button>
            {/each}
          {/if}
        </div>
      {/if}
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
    <button type="button" data-nav onclick={() => setOffset(QUICK_OFFSET_FIFTEEN_MIN)}>
      in 15 min
    </button>
    <button type="button" data-nav onclick={() => setOffset(QUICK_OFFSET_ONE_HOUR_MIN)}>
      in 1 h
    </button>
    <button
      type="button"
      data-nav
      onclick={() => shiftTime(-QUICK_OFFSET_FIFTEEN_MIN)}
    >
      Earlier
    </button>
    <button
      type="button"
      data-nav
      onclick={() => shiftTime(QUICK_OFFSET_FIFTEEN_MIN)}
    >
      Later
    </button>
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
            const parts = favourite.label.split(FAVOURITE_LABEL_SEPARATOR)
            fromText = parts[0] ?? favourite.from
            toText = parts[1] ?? favourite.to
            fromSelectedText = fromText
            toSelectedText = toText
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
  {:else if selectedConnection}
    <button
      type="button"
      class="back-button"
      data-nav
      onclick={() => (selectedIndex = null)}
    >
      ← All connections
    </button>
    <ol class="connection-list">
      {#each [selectedConnection] as connection, index (index)}
        {@const tightTransfers = tightTransferMinutes(connection)}
        {@const affected = affectedAlert(connection)}
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

          {#if affected}
            <p class="transfer-warning disruption" role="status">
              ⚠ Disruption: {affected.header}
            </p>
          {:else if tightTransfers.length > 0}
            <p class="transfer-warning" role="status">
              ⚠ Tight transfer: {Math.min(...tightTransfers)} min to change
            </p>
          {/if}

          <div class="legs">
            {#each connection.legs as leg, legIndex (legIndex)}
              {@const legKey = `${index}-${legIndex}`}
              <div class="leg-detail">
                <div class="leg-head">
                  <span class="route-bar" style={routeStyle(leg.route_color)}>
                    {routeLabel(leg.route, leg.mode)}
                  </span>
                  <span class="leg-stops">
                    {leg.from_name}{leg.from_platform ? ` (${leg.from_platform})` : ''}
                    →
                    {leg.to_name}{leg.to_platform ? ` (${leg.to_platform})` : ''}
                  </span>
                  <span class="leg-time">
                    {formatTime(leg.departure)}–{formatTime(leg.arrival)}
                  </span>
                </div>

                {#if leg.headsign}
                  <p class="leg-meta">towards {leg.headsign}</p>
                {/if}
                {#if leg.operator}
                  <p class="leg-meta">{leg.operator}</p>
                {/if}

                {#if leg.intermediate_stops.length > 0}
                  <button
                    type="button"
                    class="details-toggle"
                    data-nav
                    onclick={() => toggleDetails(legKey)}
                  >
                    {expanded[legKey] ? 'Hide' : 'Show'}
                    {leg.intermediate_stops.length} intermediate stop(s)
                  </button>
                  {#if expanded[legKey]}
                    <ol class="intermediate">
                      {#each leg.intermediate_stops as stop, stopIndex (stopIndex)}
                        <li>
                          <span>{formatTime(stop.departure ?? stop.arrival ?? '')}</span>
                          <span>{stop.name}</span>
                          {#if stop.platform}
                            <span class="platform">{stop.platform}</span>
                          {/if}
                        </li>
                      {/each}
                    </ol>
                  {/if}
                {/if}
              </div>
            {/each}
          </div>
        </li>
      {/each}
    </ol>
  {:else}
    <ol class="connection-list compact">
      {#each connections as connection, index (index)}
        {@const legs = transitLegs(connection)}
        <li>
          <button
            type="button"
            class="connection-card"
            data-nav
            onclick={() => (selectedIndex = index)}
          >
            <div class="card-top">
              <strong>
                {formatTime(connection.departure)} → {formatTime(connection.arrival)}
              </strong>
              <span>
                {connection.duration_minutes} min ·
                {connection.transfers === 0
                  ? 'direct'
                  : `${connection.transfers} transfer(s)`}
              </span>
            </div>

            <div class="route-flow">
              {#each legs as leg, legIndex (legIndex)}
                {#if legIndex > 0}
                  <span class="transfer-icon" aria-label="Walk">🚶‍♂️ →</span>
                {/if}
                <span class="route-chip" style={routeStyle(leg.route_color)}>
                  {routeLabel(leg.route, leg.mode)}
                </span>
              {/each}
            </div>

            <p class="card-from">from {legs[0]?.from_name ?? ''}</p>
          </button>
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

  .place-field {
    position: relative;
  }

  .suggestions {
    position: absolute;
    z-index: 20;
    top: 100%;
    right: 0;
    left: 0;
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid #2d3a49;
    border-radius: 10px;
    background: #10161d;
    box-shadow: 0 12px 24px rgb(0 0 0 / 45%);
  }

  .suggestions button {
    display: block;
    width: 100%;
    min-height: 48px;
    padding: 0 12px;
    border: 0;
    border-bottom: 1px solid #1f2a36;
    background: transparent;
    color: var(--color-text);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .suggestions .empty {
    margin: 0;
    padding: 12px;
    color: var(--color-muted);
    font-size: 0.82rem;
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

  .back-button {
    min-height: 44px;
    align-self: flex-start;
    padding: 0 14px;
    border: 1px solid #2d3a49;
    border-radius: 999px;
    background: #18212b;
    color: #bde9ff;
    font-weight: 700;
    cursor: pointer;
  }

  .connection-card {
    display: block;
    width: 100%;
    padding: 12px;
    border: 1px solid #263241;
    border-left: 4px solid var(--color-accent);
    border-radius: 10px;
    background: var(--color-surface);
    color: var(--color-text);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .card-top {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }

  .card-top strong {
    font-size: 1.1rem;
    font-variant-numeric: tabular-nums;
  }

  .card-top span {
    color: var(--color-muted);
    font-size: 0.84rem;
  }

  .route-flow {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .transfer-icon {
    color: var(--color-muted);
    font-size: 0.95rem;
    white-space: nowrap;
  }

  .card-from {
    margin: 8px 0 0;
    color: var(--color-muted);
    font-size: 0.8rem;
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

  .transfer-warning {
    margin: 6px 0 0;
    padding: 6px 10px;
    border-radius: 8px;
    background: #4a3410;
    color: #ffd58a;
    font-size: 0.78rem;
    font-weight: 700;
  }

  .transfer-warning.disruption {
    background: #4b1616;
    color: #ffb4b4;
  }

  .leg-detail {
    padding: 8px 0;
    border-bottom: 1px solid #1f2a36;
  }

  .leg-detail:last-child {
    border-bottom: 0;
  }

  .leg-head {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .route-bar {
    display: grid;
    place-items: center;
    min-width: 56px;
    min-height: 34px;
    padding: 0 10px;
    border-radius: 6px;
    background: #e8edf2;
    color: #0b0f14;
    font-weight: 800;
  }

  .route-chip {
    display: grid;
    place-items: center;
    min-width: 56px;
    min-height: 34px;
    padding: 0 10px;
    border-radius: 6px;
    background: #8b5cf6;
    color: #fff;
    font-size: 0.85rem;
    font-weight: 800;
  }

  .leg-meta {
    margin: 4px 0 0 66px;
    color: var(--color-muted);
    font-size: 0.78rem;
  }

  .details-toggle {
    min-height: 40px;
    margin: 6px 0 0 66px;
    padding: 0 12px;
    border: 1px solid #2d3a49;
    border-radius: 999px;
    background: transparent;
    color: #bde9ff;
    font-size: 0.78rem;
    font-weight: 700;
    cursor: pointer;
  }

  .intermediate {
    margin: 8px 0 0 66px;
    padding: 0;
    list-style: none;
  }

  .intermediate li {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 0;
    color: var(--color-muted);
    font-size: 0.8rem;
  }

  .intermediate .platform {
    margin-left: auto;
    color: var(--color-text);
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
