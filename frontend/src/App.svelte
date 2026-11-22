<script lang="ts">
  import { onMount } from 'svelte'
  import AlertList from './components/AlertList.svelte'
  import ConnectionList from './components/ConnectionList.svelte'
  import DepartureList from './components/DepartureList.svelte'
  import DelayMetricsCard from './components/DelayMetricsCard.svelte'
  import NearbyMap from './components/NearbyMap.svelte'
  import StatusBanner from './components/StatusBanner.svelte'
  import StopSelector from './components/StopSelector.svelte'
  import TopNavBar from './components/TopNavBar.svelte'
  import TransferRiskList from './components/TransferRiskList.svelte'
  import {
    fetchAlerts,
    fetchConnections,
    fetchHealth,
    fetchLiveDepartures,
    fetchMetrics,
    fetchNearbyStops,
    fetchSuggestedStops,
  } from './lib/api'
  import { loadFavourites, saveFavourites } from './lib/favourites'
  import { activeView, installNavigation } from './lib/navigation'
  import type {
    Connection,
    Departure,
    FavouriteConnection,
    HealthResponse,
    Metrics,
    NearbyStop,
    ServiceAlert,
  } from './lib/types'

  const POLL_INTERVAL_MS = 15_000
  const STOP_STORAGE_KEY = 'transit-kiosk-stop'

  let stops = $state<NearbyStop[]>([])
  let selectedStopId = $state<string | null>(null)
  let nearbyStops = $state<NearbyStop[]>([])
  let nearbyOpen = $state(false)
  let nearbyLoading = $state(false)
  let connections = $state<Connection[]>([])
  let connectionLoading = $state(false)
  let connectionError = $state<string | null>(null)
  let favourites = $state<FavouriteConnection[]>([])
  let alerts = $state<ServiceAlert[]>([])
  let alertLoading = $state(false)
  let alertError = $state<string | null>(null)
  let departures = $state<Departure[]>([])
  let arriveBy = $state(false)
  let metrics = $state<Metrics | null>(null)
  let health = $state<HealthResponse | null>(null)
  let lastUpdated = $state<Date | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(true)
  let online = $state(true)

  let refreshController: AbortController | null = null
  let disposed = false

  const selectedStopName = $derived(
    stops.find((stop) => stop.stop_id === selectedStopId)?.name ??
      nearbyStops.find((stop) => stop.stop_id === selectedStopId)?.name ??
      'Transit stop',
  )

  const stopNames = $derived(
    new Map(
      [...stops, ...nearbyStops].map((stop) => [stop.stop_id, stop.name] as const),
    ),
  )

  const mapCenter = $derived.by(() => {
    const stop = [...stops, ...nearbyStops].find(
      (item) => item.stop_id === selectedStopId,
    )
    return stop && stop.latitude !== null && stop.longitude !== null
      ? { latitude: stop.latitude, longitude: stop.longitude }
      : null
  })

  function isAbortError(caught: unknown): boolean {
    return caught instanceof DOMException && caught.name === 'AbortError'
  }

  function savedStop(): string | null {
    try {
      return window.localStorage.getItem(STOP_STORAGE_KEY)
    } catch {
      return null
    }
  }

  function rememberStop(stopId: string): void {
    try {
      window.localStorage.setItem(STOP_STORAGE_KEY, stopId)
    } catch {
      // Storage can be unavailable in locked-down kiosk browsers.
    }
  }

  function pickDefaultStop(nextStops: NearbyStop[]): string | null {
    if (nextStops.length === 0) return null
    const saved = savedStop()
    if (saved !== null && nextStops.some((stop) => stop.stop_id === saved)) {
      return saved
    }
    return nextStops[0].stop_id
  }

  async function loadAlerts(controller: AbortController): Promise<void> {
    alertLoading = true
    try {
      alerts = await fetchAlerts(controller.signal)
      alertError = null
    } catch (caught) {
      if (isAbortError(caught) || disposed) return
      alertError = caught instanceof Error ? caught.message : 'Unable to load service alerts'
    } finally {
      alertLoading = false
    }
  }

  async function refresh(
    options: { initial?: boolean; lat?: number; lon?: number } = {},
  ): Promise<void> {
    if (disposed) return

    refreshController?.abort()
    const controller = new AbortController()
    refreshController = controller
    if (options.initial) loading = true

    try {
      const [nextHealth, nextStops, nextMetrics] = await Promise.all([
        fetchHealth(controller.signal),
        fetchSuggestedStops(controller.signal, options.lat, options.lon),
        fetchMetrics(controller.signal),
      ])

      if (controller.signal.aborted || disposed) return

      health = nextHealth
      stops = nextStops
      metrics = nextMetrics

      if (
        selectedStopId === null ||
        !nextStops.some((stop) => stop.stop_id === selectedStopId)
      ) {
        selectedStopId = pickDefaultStop(nextStops)
      }

      if (selectedStopId === null) {
        departures = []
      } else {
        departures = await fetchLiveDepartures(selectedStopId, controller.signal, 20, arriveBy)
      }

      await loadAlerts(controller)

      if (controller.signal.aborted || disposed) return

      lastUpdated = new Date()
      error = null
    } catch (caught) {
      if (isAbortError(caught) || disposed) return
      error = caught instanceof Error ? caught.message : 'Unable to reach the transit service'
    } finally {
      if (refreshController === controller) {
        refreshController = null
        loading = false
      }
    }
  }

  function toggleArriveBy(value: boolean): void {
    if (value === arriveBy) return
    arriveBy = value
    departures = []
    loading = true
    void refresh()
  }

  function selectStop(stopId: string): void {
    if (stopId === selectedStopId) return
    nearbyOpen = false
    nearbyStops = []
    selectedStopId = stopId
    rememberStop(stopId)
    departures = []
    loading = true
    void refresh()
  }

  async function toggleNearby(): Promise<void> {
    if (nearbyOpen) {
      nearbyOpen = false
      nearbyStops = []
      return
    }

    const anchor = selectedStopId
    if (anchor === null) return

    nearbyOpen = true
    nearbyLoading = true
    nearbyStops = []
    try {
      nearbyStops = await fetchNearbyStops(anchor)
    } catch (caught) {
      error = caught instanceof Error ? caught.message : 'Unable to load nearby stops'
    } finally {
      nearbyLoading = false
    }
  }

  function locate(): void {
    if (!navigator.geolocation) {
      error = 'Geolocation is not available on this device'
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        void refresh({ lat: position.coords.latitude, lon: position.coords.longitude })
      },
      () => {
        error = 'Location permission denied; showing stops near the configured area'
      },
      { timeout: 5000, maximumAge: 300_000 },
    )
  }

  async function searchConnections(
    from: string,
    to: string,
    time?: string,
    arriveBy = false,
  ): Promise<void> {
    connectionLoading = true
    connectionError = null
    connections = []
    try {
      connections = await fetchConnections(from, to, undefined, 3, time, arriveBy)
    } catch (caught) {
      connectionError = caught instanceof Error ? caught.message : 'Unable to plan connections'
    } finally {
      connectionLoading = false
    }
  }

  function saveFavourite(from: string, to: string, label: string): void {
    const next = [
      ...favourites.filter((item) => item.from !== from || item.to !== to),
      { from, to, label },
    ]
    favourites = next
    saveFavourites(next)
  }

  function selectFavourite(favourite: FavouriteConnection): void {
    void searchConnections(favourite.from, favourite.to)
  }

  onMount(() => {
    online = navigator.onLine
    favourites = loadFavourites()

    const handleOnline = () => {
      online = true
      void refresh()
    }
    const handleOffline = () => {
      online = false
    }

    const stopNavigation = installNavigation()
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    void refresh({ initial: true })
    const timer = window.setInterval(() => {
      if (navigator.onLine) void refresh()
    }, POLL_INTERVAL_MS)

    return () => {
      disposed = true
      window.clearInterval(timer)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      refreshController?.abort()
      stopNavigation()
    }
  })
</script>

<div class="kiosk">
  <TopNavBar />

  {#if $activeView === 'live'}
    <StopSelector
      {stops}
      {selectedStopId}
      {nearbyStops}
      {nearbyOpen}
      {nearbyLoading}
      onSelect={selectStop}
      onToggleNearby={() => void toggleNearby()}
      onSelectNearby={(stop) => selectStop(stop.stop_id)}
      onLocate={locate}
    />
    {#if nearbyOpen}
      <NearbyMap
        stops={nearbyStops}
        center={mapCenter}
        {selectedStopId}
        onSelect={(stop) => selectStop(stop.stop_id)}
      />
    {/if}
  {/if}

  <StatusBanner {health} {error} {online} {lastUpdated} />

  <main class="kiosk-content">
    {#if $activeView === 'live'}
      <DepartureList
        {departures}
        {loading}
        stopName={selectedStopName}
        {arriveBy}
        onToggleArriveBy={toggleArriveBy}
      />
    {:else if $activeView === 'delays'}
      <DelayMetricsCard {metrics} {loading} />
    {:else if $activeView === 'transfers'}
      <TransferRiskList risks={metrics?.transfer_risks ?? []} stops={[...stops, ...nearbyStops]} {loading} />
    {:else if $activeView === 'connections'}
      <ConnectionList
        stops={[...stops, ...nearbyStops]}
        {selectedStopId}
        {connections}
        loading={connectionLoading}
        error={connectionError}
        {favourites}
        onSearch={(from, to, time, arriveBy) =>
          void searchConnections(from, to, time, arriveBy)}
        onSave={saveFavourite}
        onSelectFavourite={selectFavourite}
      />
    {:else}
      <AlertList
        {alerts}
        loading={alertLoading}
        error={alertError}
        {stopNames}
      />
    {/if}
  </main>

  <footer class="attribution">
    Data:
    <a href="https://transitous.org/sources/" target="_blank" rel="noopener noreferrer">
      Transitous sources
    </a>
    ·
    <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">
      © OpenStreetMap contributors
    </a>
  </footer>
</div>

<style>
  .kiosk {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background:
      radial-gradient(circle at 18% 0%, rgb(53 196 107 / 7%), transparent 42%),
      radial-gradient(circle at 92% 8%, rgb(125 211 252 / 6%), transparent 36%),
      var(--color-bg);
  }

  .kiosk-content {
    flex: 1;
    min-height: 0;
    padding: 8px 10px 10px;
    overflow: hidden;
  }

  .attribution {
    flex: 0 0 auto;
    padding: 0 10px 4px;
    color: var(--color-muted);
    font-size: 0.66rem;
    text-align: right;
  }

  .attribution a {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
</style>
