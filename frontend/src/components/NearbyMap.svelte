<script lang="ts">
  import type { NearbyStop } from '../lib/types'
  import {
    MAP_BASELINE_Y,
    MAP_MARGIN_X,
    MAP_PLOT_SIZE,
    MAP_RIGHT_X,
    MAP_TOP_Y,
    MAP_VIEWBOX_SIZE,
    MAX_MAP_STOPS,
    MIN_COORD_SPAN,
  } from '../lib/constants'

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

  const bounds = $derived.by(() => {
    if (located.length === 0 || center === null) return null
    const lats = [center.latitude, ...located.map((stop) => stop.latitude)]
    const lons = [center.longitude, ...located.map((stop) => stop.longitude)]
    const minLat = Math.min(...lats)
    const maxLat = Math.max(...lats)
    const minLon = Math.min(...lons)
    const maxLon = Math.max(...lons)
    return {
      minLat,
      minLon,
      latSpan: Math.max(maxLat - minLat, MIN_COORD_SPAN),
      lonSpan: Math.max(maxLon - minLon, MIN_COORD_SPAN),
    }
  })

  function project(lat: number, lon: number): { x: number; y: number } | null {
    if (bounds === null) return null
    return {
      x: MAP_MARGIN_X + ((lon - bounds.minLon) / bounds.lonSpan) * MAP_PLOT_SIZE,
      y: MAP_BASELINE_Y - ((lat - bounds.minLat) / bounds.latSpan) * MAP_PLOT_SIZE,
    }
  }

  const mapped = $derived(
    located
      .slice(0, MAX_MAP_STOPS)
      .map((stop) => ({ stop, point: project(stop.latitude, stop.longitude) }))
      .filter(
        (item): item is { stop: LocatedStop; point: { x: number; y: number } } =>
          item.point !== null,
      ),
  )

  const centerPoint = $derived(
    center === null ? null : project(center.latitude, center.longitude),
  )

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
  <svg
    viewBox={`0 0 ${MAP_VIEWBOX_SIZE} ${MAP_VIEWBOX_SIZE}`}
    role="img"
    aria-label="Positions of nearby stops"
  >
    <line
      x1={MAP_MARGIN_X}
      y1={MAP_BASELINE_Y}
      x2={MAP_RIGHT_X}
      y2={MAP_BASELINE_Y}
      class="axis"
    />
    <line
      x1={MAP_MARGIN_X}
      y1={MAP_TOP_Y}
      x2={MAP_MARGIN_X}
      y2={MAP_BASELINE_Y}
      class="axis"
    />

    {#if centerPoint}
      <circle cx={centerPoint.x} cy={centerPoint.y} r="7" class="center-marker" />
    {/if}

    {#each mapped as item (item.stop.stop_id)}
      <g
        class:selected={selectedStopId === item.stop.stop_id}
        role="button"
        tabindex="0"
        aria-label={`${item.stop.name}, ${item.stop.distance_m ?? 0} metres away`}
        onclick={() => activate(item.stop)}
        onkeydown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') activate(item.stop)
        }}
      >
        <circle cx={item.point.x} cy={item.point.y} r="16" class="stop-marker" />
        <text
          x={item.point.x}
          y={item.point.y + 6}
          class="stop-icon"
          text-anchor="middle"
        >
          {modeIcon(item.stop.mode)}
        </text>
        <text
          x={item.point.x}
          y={item.point.y - 24}
          class="stop-label"
          text-anchor="middle"
        >
          {item.stop.name.split(',')[0]}
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
