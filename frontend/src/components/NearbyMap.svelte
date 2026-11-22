<script lang="ts">
  import type { NearbyStop } from '../lib/types'

  interface Props {
    stops: NearbyStop[]
    center: { latitude: number; longitude: number } | null
    selectedStopId: string | null
    onSelect: (stop: NearbyStop) => void
  }

  let { stops, center, selectedStopId, onSelect }: Props = $props()

  type LocatedStop = NearbyStop & { latitude: number; longitude: number }

  const located = $derived(
    stops.filter(
      (stop): stop is LocatedStop =>
        stop.latitude !== null && stop.longitude !== null,
    ),
  )

  const mapped = $derived.by(() => {
    if (located.length === 0 || center === null) return []
    const lats = [center.latitude, ...located.map((stop) => stop.latitude)]
    const lons = [center.longitude, ...located.map((stop) => stop.longitude)]
    const minLat = Math.min(...lats)
    const maxLat = Math.max(...lats)
    const minLon = Math.min(...lons)
    const maxLon = Math.max(...lons)
    const latSpan = Math.max(maxLat - minLat, 0.0005)
    const lonSpan = Math.max(maxLon - minLon, 0.0005)

    const project = (lat: number, lon: number) => ({
      x: 30 + ((lon - minLon) / lonSpan) * 260,
      y: 290 - ((lat - minLat) / latSpan) * 260,
    })

    return located.slice(0, 12).map((stop) => ({
      stop,
      ...project(stop.latitude, stop.longitude),
    }))
  })

  const centerPoint = $derived.by(() => {
    if (center === null || located.length === 0) return null
    const lats = [center.latitude, ...located.map((stop) => stop.latitude)]
    const lons = [center.longitude, ...located.map((stop) => stop.longitude)]
    const minLat = Math.min(...lats)
    const maxLat = Math.max(...lats)
    const minLon = Math.min(...lons)
    const maxLon = Math.max(...lons)
    const latSpan = Math.max(maxLat - minLat, 0.0005)
    const lonSpan = Math.max(maxLon - minLon, 0.0005)
    return {
      x: 30 + ((center.longitude - minLon) / lonSpan) * 260,
      y: 290 - ((center.latitude - minLat) / latSpan) * 260,
    }
  })

  function modeIcon(mode: string | null): string {
    const value = (mode ?? '').toLowerCase()
    if (value.includes('bus') || value.includes('coach')) return '🚌'
    if (value.includes('tram') || value.includes('light_rail')) return '🚊'
    if (value.includes('rail') || value.includes('train')) return '🚆'
    return '•'
  }

  function activate(stop: NearbyStop): void {
    onSelect(stop)
  }
</script>

<section class="nearby-map" aria-label="Nearby stop map">
  <svg viewBox="0 0 320 320" role="img" aria-label="Positions of nearby stops">
    <line x1="30" y1="290" x2="290" y2="290" class="axis" />
    <line x1="30" y1="30" x2="30" y2="290" class="axis" />

    {#if centerPoint}
      <circle cx={centerPoint.x} cy={centerPoint.y} r="7" class="center-marker" />
    {/if}

    {#each mapped as point (point.stop.stop_id)}
      <g
        class:selected={selectedStopId === point.stop.stop_id}
        role="button"
        tabindex="0"
        aria-label={`${point.stop.name}, ${point.stop.distance_m ?? 0} metres away`}
        onclick={() => activate(point.stop)}
        onkeydown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') activate(point.stop)
        }}
      >
        <circle cx={point.x} cy={point.y} r="16" class="stop-marker" />
        <text x={point.x} y={point.y + 6} class="stop-icon" text-anchor="middle">
          {modeIcon(point.stop.mode)}
        </text>
        <text x={point.x} y={point.y - 24} class="stop-label" text-anchor="middle">
          {point.stop.name.split(',')[0]}
        </text>
      </g>
    {/each}
  </svg>
</section>

<style>
  .nearby-map {
    flex-basis: 100%;
    height: 300px;
    border: 1px solid #263241;
    border-radius: 12px;
    background: #10161d;
  }

  svg {
    width: 100%;
    height: 100%;
  }

  .axis {
    stroke: #2d3a49;
    stroke-width: 1;
  }

  .center-marker {
    fill: #7dd3fc;
    opacity: 0.85;
  }

  .stop-marker {
    fill: #18212b;
    stroke: #2d3a49;
    stroke-width: 2;
  }

  .selected .stop-marker {
    fill: #123d25;
    stroke: var(--color-accent);
  }

  .stop-icon {
    font-size: 16px;
  }

  .stop-label {
    fill: var(--color-muted);
    font-size: 11px;
  }
</style>
