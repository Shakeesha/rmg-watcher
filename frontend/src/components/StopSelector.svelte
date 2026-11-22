<script lang="ts">
  import { fetchPlaces, resolvePlace } from '../lib/api'
  import { AUTOCOMPLETE_DEBOUNCE_MS } from '../lib/constants'
  import { formatDistance, transportIcon } from '../lib/format'
  import type { NearbyStop, PlaceResult, Stop } from '../lib/types'

  interface Props {
    stops: Stop[]
    selectedStopId: string | null
    nearbyStops: NearbyStop[]
    nearbyOpen: boolean
    nearbyLoading: boolean
    onSelect: (stopId: string) => void
    onToggleNearby: () => void
    onSelectNearby: (stop: NearbyStop) => void
    onLocate: () => void
    onSelectPlace: (place: PlaceResult) => void
  }

  let {
    stops,
    selectedStopId,
    nearbyStops,
    nearbyOpen,
    nearbyLoading,
    onSelect,
    onToggleNearby,
    onSelectNearby,
    onLocate,
    onSelectPlace,
  }: Props = $props()

  let query = $state('')
  let suggestions = $state<PlaceResult[]>([])
  let searchLoading = $state(false)
  let searchController: AbortController | null = null

  $effect(() => {
    const term = query.trim()
    if (term.length < 2) {
      suggestions = []
      return
    }
    const timer = window.setTimeout(async () => {
      searchController?.abort()
      const controller = new AbortController()
      searchController = controller
      searchLoading = true
      try {
        suggestions = await fetchPlaces(term, controller.signal)
      } catch {
        suggestions = []
      } finally {
        searchLoading = false
      }
    }, AUTOCOMPLETE_DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      searchController?.abort()
    }
  })

  async function choosePlace(place: PlaceResult): Promise<void> {
    query = ''
    suggestions = []
    let selected = place
    try {
      selected = (await resolvePlace(place.id)) ?? place
    } catch {
      selected = place
    }
    onSelectPlace(selected)
  }

  const filteredStops = $derived(
    query.trim() === ''
      ? stops
      : stops.filter((stop) => stop.name.toLowerCase().includes(query.trim().toLowerCase())),
  )

  const filteredNearby = $derived(
    query.trim() === ''
      ? nearbyStops
      : nearbyStops.filter((stop) =>
          stop.name.toLowerCase().includes(query.trim().toLowerCase()),
        ),
  )

</script>

<section class="stop-selector" aria-label="Choose a stop">
  <span class="selector-label">Stop</span>
  <div class="search-wrap">
    <input
      class="stop-search"
      type="search"
      placeholder="Search any stop in Germany"
      aria-label="Search any stop in Germany"
      bind:value={query}
      data-nav
    />

    {#if query.trim().length >= 2}
      <div class="suggestions" role="listbox" aria-label="Stop suggestions">
        {#if searchLoading}
          <p class="empty">Searching…</p>
        {:else if suggestions.length === 0}
          <p class="empty">No stops found.</p>
        {:else}
          {#each suggestions as place (place.id)}
            <button
              type="button"
              role="option"
              aria-selected={selectedStopId === place.id}
              data-nav
              onclick={() => choosePlace(place)}
            >
              <span class="mode" aria-hidden="true">{transportIcon(place.mode)}</span>
              <span class="suggestion-name">{place.name}</span>
              <span class="suggestion-type">{place.type}</span>
            </button>
          {/each}
        {/if}
      </div>
    {/if}
  </div>

  <div class="stop-buttons" role="group" aria-label="Configured stops">
    {#each filteredStops as stop (stop.stop_id)}
      <button
        type="button"
        class="stop-button"
        class:active={selectedStopId === stop.stop_id}
        data-nav
        aria-pressed={selectedStopId === stop.stop_id}
        onclick={() => onSelect(stop.stop_id)}
      >
        <span class="mode" aria-hidden="true">{transportIcon(stop.mode ?? null)}</span>
        {stop.name}
      </button>
    {:else}
      <span class="empty">No stops configured</span>
    {/each}

    <button
      type="button"
      class="nearby-toggle"
      class:active={nearbyOpen}
      data-nav
      aria-pressed={nearbyOpen}
      onclick={onToggleNearby}
    >
      Nearby
    </button>

    <button type="button" class="locate-button" data-nav onclick={onLocate} title="Use my location">
      Locate
    </button>
  </div>

  {#if nearbyOpen}
    <div class="nearby-row" role="group" aria-label="Nearby stops">
      {#if nearbyLoading}
        <span class="empty">Loading nearby stops…</span>
      {:else if nearbyStops.length === 0}
        <span class="empty">No nearby stops found.</span>
      {:else}
        {#each filteredNearby as stop (stop.stop_id)}
          <button
            type="button"
            class="nearby-button"
            class:active={selectedStopId === stop.stop_id}
            data-nav
            aria-pressed={selectedStopId === stop.stop_id}
            onclick={() => onSelectNearby(stop)}
          >
            <span class="mode" aria-hidden="true">{transportIcon(stop.mode ?? null)}</span>
            {stop.name}
            <span class="distance">{formatDistance(stop.distance_m)}</span>
          </button>
        {/each}
      {/if}
    </div>
  {/if}
</section>

<style>
  .stop-selector {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 10px;
    padding: 6px 12px;
    border-bottom: 1px solid #1f2a36;
    background: #0f151c;
  }

  .selector-label {
    color: var(--color-muted);
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .stop-search {
    flex: 1 1 100%;
    min-height: 48px;
    padding: 0 12px;
    border: 1px solid #2d3a49;
    border-radius: 10px;
    background: #18212b;
    color: var(--color-text);
    font: inherit;
  }

  .search-wrap {
    position: relative;
    flex: 1 1 100%;
  }

  .suggestions {
    position: absolute;
    z-index: 20;
    top: 100%;
    right: 0;
    left: 0;
    max-height: 320px;
    overflow-y: auto;
    border: 1px solid #2d3a49;
    border-radius: 10px;
    background: #10161d;
    box-shadow: 0 12px 24px rgb(0 0 0 / 45%);
  }

  .suggestions button {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    min-height: 54px;
    padding: 0 12px;
    border: 0;
    border-bottom: 1px solid #1f2a36;
    background: transparent;
    color: var(--color-text);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .suggestions button:hover,
  .suggestions button:focus-visible {
    background: #18212b;
  }

  .suggestion-name {
    min-width: 0;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .suggestion-type {
    color: var(--color-muted);
    font-size: 0.72rem;
  }

  .stop-buttons {
    display: flex;
    flex: 1 1 auto;
    gap: 8px;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .stop-buttons::-webkit-scrollbar {
    display: none;
  }

  .stop-button,
  .nearby-toggle,
  .locate-button {
    flex: 0 0 auto;
    max-width: 320px;
    min-height: 52px;
    padding: 0 18px;
    overflow: hidden;
    border: 1px solid #2d3a49;
    border-radius: 999px;
    background: #18212b;
    color: var(--color-text);
    font-weight: 700;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
  }

  .mode {
    margin-right: 6px;
    font-size: 1.1rem;
  }

  .stop-button.active {
    border-color: #7dd3fc;
    background: #123247;
    color: #e0f5ff;
  }

  .nearby-toggle {
    border-color: #7dd3fc;
    background: transparent;
    color: #bde9ff;
  }

  .nearby-toggle.active {
    background: #123247;
    color: #e0f5ff;
  }

  .locate-button {
    border-color: #7dd3fc;
    background: transparent;
    color: #bde9ff;
  }

  .nearby-row {
    display: flex;
    flex-basis: 100%;
    gap: 8px;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .nearby-row::-webkit-scrollbar {
    display: none;
  }

  .nearby-button {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 8px;
    min-height: 48px;
    padding: 0 12px;
    border: 1px solid #2d3a49;
    border-radius: 999px;
    background: #141b23;
    color: var(--color-text);
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
  }

  .nearby-button.active {
    border-color: var(--color-accent);
    background: #123d25;
    color: #d9ffe7;
  }

  .distance {
    color: var(--color-muted);
    font-size: 0.75rem;
    font-variant-numeric: tabular-nums;
  }

  .empty {
    color: var(--color-muted);
    font-size: 0.85rem;
  }
</style>
