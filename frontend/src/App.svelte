<script lang="ts">
  import { onMount } from 'svelte'
  import ConnectionList from './components/ConnectionList.svelte'
  import DepartureList from './components/DepartureList.svelte'
  import DelayMetricsCard from './components/DelayMetricsCard.svelte'
  import StatusBanner from './components/StatusBanner.svelte'
  import StopSelector from './components/StopSelector.svelte'
  import TopNavBar from './components/TopNavBar.svelte'
  import TransferRiskList from './components/TransferRiskList.svelte'
  import {
    fetchConnections,
    fetchDepartures,
    fetchHealth,
    fetchLiveDepartures,
    fetchMetrics,
    fetchNearbyStops,
    fetchStops,
  } from './lib/api'
  import { activeView, installNavigation } from './lib/navigation'
  import type {
    Connection,
    Departure,
    HealthResponse,
    Metrics,
    NearbyStop,
    Stop,
  } from './lib/types'

  const POLL_INTERVAL_MS = 15_000
  const STOP_STORAGE_KEY = 'transit-kiosk-stop'

  let stops = $state<Stop[]>([])
  let selectedStopId = $state<string | null>(null)
  let liveStopId = $state<string | null>(null)
  let liveStopName = $state<string | null>(null)
  let nearbyStops = $state<NearbyStop[]>([])
  let nearbyOpen = $state(false)
  let nearbyLoading = $state(false)
  let connections = $state<Connection[]>([])
  let connectionLoading = $state(false)
  let connectionError = $state<string | null>(null)
  let departures = $state<Departure[]>([])
  let metrics = $state<Metrics | null>(null)
  let health = $state<HealthResponse | null>(null)
  let lastUpdated = $state<Date | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(true)
  let online = $state(true)

  let refreshController: AbortController | null = null
  let disposed = false

  const selectedStopName = $derived(
    liveStopId !== null
      ? (liveStopName ?? 'Nearby stop')
      : (stops.find((stop) => stop.stop_id === selectedStopId)?.name ?? 'Transit stop'),
  )

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

  function pickDefaultStop(nextStops: Stop[]): string | null {
    if (nextStops.length === 0) return null
    const saved = savedStop()
    if (saved !== null && nextStops.some((stop) => stop.stop_id === saved)) {
      return saved
    }
    return (
      nextStops.find((stop) => stop.stop_id === 'luisenplatz')?.stop_id ??
      nextStops[0].stop_id
    )
  }

  async function refresh(options: { initial?: boolean } = {}): Promise<void> {
    if (disposed) return

    refreshController?.abort()
    const controller = new AbortController()
    refreshController = controller
    if (options.initial) loading = true

    try {
      const [nextHealth, nextStops, nextMetrics] = await Promise.all([
        fetchHealth(controller.signal),
        fetchStops(controller.signal),
        fetchMetrics(controller.signal),
      ])

      if (controller.signal.aborted || disposed) return

      health = nextHealth
      stops = nextStops
      metrics = nextMetrics

      if (
        liveStopId === null &&
        (selectedStopId === null ||
          !nextStops.some((stop) => stop.stop_id === selectedStopId))
      ) {
        selectedStopId = pickDefaultStop(nextStops)
      }

      if (liveStopId !== null) {
        departures = await fetchLiveDepartures(liveStopId, controller.signal)
      } else if (selectedStopId === null) {
        departures = []
      } else {
        departures = await fetchDepartures(selectedStopId, controller.signal)
      }

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

  function selectStop(stopId: string): void {
    if (stopId === selectedStopId && liveStopId === null) return
    liveStopId = null
    liveStopName = null
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

    const anchor = liveStopId ?? selectedStopId
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

  async function selectNearbyStop(stop: NearbyStop): Promise<void> {
    if (stop.stop_id === liveStopId) return

    refreshController?.abort()
    const controller = new AbortController()
    refreshController = controller

    liveStopId = stop.stop_id
    liveStopName = stop.name
    selectedStopId = stop.stop_id
    departures = []
    loading = true
    error = null

    try {
      departures = await fetchLiveDepartures(stop.stop_id, controller.signal)
      lastUpdated = new Date()
    } catch (caught) {
      if (isAbortError(caught) || disposed) return
      error = caught instanceof Error ? caught.message : 'Unable to load nearby departures'
    } finally {
      if (refreshController === controller) {
        refreshController = null
        loading = false
      }
    }
  }

  async function searchConnections(from: string, to: string): Promise<void> {
    connectionLoading = true
    connectionError = null
    connections = []
    try {
      connections = await fetchConnections(from, to)
    } catch (caught) {
      connectionError = caught instanceof Error ? caught.message : 'Unable to plan connections'
    } finally {
      connectionLoading = false
    }
  }

  onMount(() => {
    online = navigator.onLine

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
      onSelectNearby={(stop) => void selectNearbyStop(stop)}
    />
  {/if}

  <StatusBanner {health} {error} {online} {lastUpdated} />

  <main class="kiosk-content">
    {#if $activeView === 'live'}
      <DepartureList {departures} {loading} stopName={selectedStopName} />
    {:else if $activeView === 'delays'}
      <DelayMetricsCard {metrics} {loading} />
    {:else if $activeView === 'transfers'}
      <TransferRiskList risks={metrics?.transfer_risks ?? []} {stops} {loading} />
    {:else}
      <ConnectionList
        {stops}
        selectedStopId={liveStopId ?? selectedStopId}
        {connections}
        loading={connectionLoading}
        error={connectionError}
        onSearch={(from, to) => void searchConnections(from, to)}
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
