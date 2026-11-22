<script lang="ts">
  import {
    MAP_BOTTOM_SHEET_LIMIT,
    MAP_ZOOM,
    MAX_MAP_STOPS,
    TILE_GRID_RADIUS,
    TILE_SIZE_PX,
  } from '../lib/constants'
  import {
    formatDistance,
    transportColor,
    transportIcon,
  } from '../lib/format'
  import type { NearbyStop } from '../lib/types'

  interface Props {
    stops: NearbyStop[]
    center: { latitude: number; longitude: number } | null
    selectedStopId: string | null
    loading: boolean
    onSelect: (stop: NearbyStop) => void
  }

  let { stops, center, selectedStopId, loading, onSelect }: Props = $props()

  let width = $state(720)
  let height = $state(420)

  type LocatedStop = NearbyStop & { latitude: number; longitude: number }

  function lonToTileX(lon: number): number {
    return ((lon + 180) / 360) * 2 ** MAP_ZOOM
  }

  function latToTileY(lat: number): number {
    const radians = (lat * Math.PI) / 180
    return ((1 - Math.asinh(Math.tan(radians)) / Math.PI) / 2) * 2 ** MAP_ZOOM
  }

  const centerTile = $derived(
    center === null
      ? null
      : {
          x: Math.floor(lonToTileX(center.longitude)),
          y: Math.floor(latToTileY(center.latitude)),
        },
  )

  const globalCenter = $derived(
    center === null
      ? null
      : {
          x: lonToTileX(center.longitude) * TILE_SIZE_PX,
          y: latToTileY(center.latitude) * TILE_SIZE_PX,
        },
  )

  const tiles = $derived.by(() => {
    if (centerTile === null || globalCenter === null) return []
    const result = []
    for (let dx = -TILE_GRID_RADIUS; dx <= TILE_GRID_RADIUS; dx += 1) {
      for (let dy = -TILE_GRID_RADIUS; dy <= TILE_GRID_RADIUS; dy += 1) {
        const x = centerTile.x + dx
        const y = centerTile.y + dy
        result.push({
          key: `${MAP_ZOOM}/${x}/${y}`,
          x,
          y,
          left: x * TILE_SIZE_PX - globalCenter.x + width / 2,
          top: y * TILE_SIZE_PX - globalCenter.y + height / 2,
        })
      }
    }
    return result
  })

  function project(lat: number, lon: number): { x: number; y: number } | null {
    if (globalCenter === null) return null
    return {
      x: lonToTileX(lon) * TILE_SIZE_PX - globalCenter.x + width / 2,
      y: latToTileY(lat) * TILE_SIZE_PX - globalCenter.y + height / 2,
    }
  }

  const located = $derived(
    stops.filter(
      (stop): stop is LocatedStop =>
        stop.latitude !== null && stop.longitude !== null,
    ),
  )

  const markers = $derived(
    located
      .slice(0, MAX_MAP_STOPS)
      .map((stop) => ({ stop, point: project(stop.latitude, stop.longitude) }))
      .filter(
        (
          item,
        ): item is { stop: LocatedStop; point: { x: number; y: number } } =>
          item.point !== null,
      ),
  )

  const centerPoint = $derived(
    center === null ? null : project(center.latitude, center.longitude),
  )
  const sheetStops = $derived(located.slice(0, MAP_BOTTOM_SHEET_LIMIT))
</script>

<section
  class="nearby-map"
  aria-label="Nearby stop map"
  bind:clientWidth={width}
  bind:clientHeight={height}
>
  <div class="map-canvas">
    {#each tiles as tile (tile.key)}
      <img
        class="map-tile"
        src={`/api/tiles/${MAP_ZOOM}/${tile.x}/${tile.y}.png`}
        alt=""
        draggable="false"
        style:left={`${tile.left}px`}
        style:top={`${tile.top}px`}
      />
    {/each}

    {#if centerPoint}
      <span class="user-halo" style:left={`${centerPoint.x}px`} style:top={`${centerPoint.y}px`}></span>
      <span class="user-dot" style:left={`${centerPoint.x}px`} style:top={`${centerPoint.y}px`}></span>
    {/if}

    {#each markers as marker (marker.stop.stop_id)}
      <button
        type="button"
        class="map-marker"
        class:selected={selectedStopId === marker.stop.stop_id}
        style:left={`${marker.point.x}px`}
        style:top={`${marker.point.y}px`}
        style:--marker-color={transportColor(marker.stop.mode)}
        aria-label={`${marker.stop.name}, ${marker.stop.distance_m ?? 0} metres away`}
        onclick={() => onSelect(marker.stop)}
      >
        <span class="marker-icon" aria-hidden="true">
          {transportIcon(marker.stop.mode)}
        </span>
      </button>
    {/each}

    <div class="nearby-sheet">
      <div class="sheet-handle" aria-hidden="true"></div>
      <h3>Nearby stops</h3>
      {#if loading}
        <p class="sheet-empty">Finding nearby stops…</p>
      {:else}
        {#each sheetStops as stop (stop.stop_id)}
          <button type="button" class="sheet-row" onclick={() => onSelect(stop)}>
            <span
              class="sheet-icon"
              style:--marker-color={transportColor(stop.mode)}
              aria-hidden="true"
            >
              {transportIcon(stop.mode)}
            </span>
            <span class="sheet-name">{stop.name}</span>
            <span class="sheet-distance">{formatDistance(stop.distance_m)}</span>
          </button>
        {:else}
          <p class="sheet-empty">No nearby stops found.</p>
        {/each}
      {/if}
    </div>
  </div>
</section>

<style>
  .nearby-map {
    flex-basis: 100%;
    height: 420px;
    overflow: hidden;
    border: 1px solid #263241;
    border-radius: 12px;
    background: #1b2430;
  }

  .map-canvas {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .map-tile {
    position: absolute;
    width: 256px;
    height: 256px;
    max-width: none;
    user-select: none;
  }

  .user-halo,
  .user-dot,
  .map-marker {
    position: absolute;
    transform: translate(-50%, -50%);
  }

  .user-halo {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: rgb(59 130 246 / 25%);
  }

  .user-dot {
    width: 12px;
    height: 12px;
    border: 2px solid #fff;
    border-radius: 50%;
    background: #3b82f6;
    box-shadow: 0 1px 4px rgb(0 0 0 / 45%);
  }

  .map-marker {
    display: grid;
    place-items: center;
    width: 46px;
    height: 46px;
    padding: 5px;
    border: 2px solid #fff;
    border-radius: 12px;
    background: #fff;
    box-shadow: 0 2px 8px rgb(0 0 0 / 45%);
    cursor: pointer;
  }

  .map-marker.selected {
    outline: 3px solid #7dd3fc;
    outline-offset: 2px;
  }

  .marker-icon {
    display: grid;
    place-items: center;
    width: 100%;
    height: 100%;
    border-radius: 7px;
    background: var(--marker-color);
    font-size: 1.05rem;
  }

  .nearby-sheet {
    position: absolute;
    right: 0;
    bottom: 0;
    left: 0;
    max-height: 160px;
    padding: 6px 12px 10px;
    overflow-y: auto;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    background: rgb(15 23 42 / 96%);
    box-shadow: 0 -6px 20px rgb(0 0 0 / 35%);
  }

  .sheet-handle {
    width: 44px;
    height: 4px;
    margin: 0 auto 8px;
    border-radius: 999px;
    background: #475569;
  }

  .nearby-sheet h3 {
    margin: 0 0 4px;
    color: var(--color-muted);
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .sheet-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    min-height: 44px;
    padding: 0 4px;
    border: 0;
    border-bottom: 1px solid #1f2a36;
    background: transparent;
    color: var(--color-text);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .sheet-icon {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    flex: 0 0 auto;
    border-radius: 6px;
    background: var(--marker-color);
    font-size: 0.95rem;
  }

  .sheet-name {
    min-width: 0;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sheet-distance {
    flex: 0 0 auto;
    color: var(--color-muted);
    font-size: 0.8rem;
  }

  .sheet-empty {
    margin: 4px 0;
    color: var(--color-muted);
    font-size: 0.84rem;
  }
</style>
