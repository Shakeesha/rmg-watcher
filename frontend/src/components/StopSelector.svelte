<script lang="ts">
  import type { Stop } from '../lib/types'

  interface Props {
    stops: Stop[]
    selectedStopId: string | null
    onSelect: (stopId: string) => void
  }

  let { stops, selectedStopId, onSelect }: Props = $props()
</script>

<section class="stop-selector" aria-label="Choose a stop">
  <span class="selector-label">Stop</span>
  <div class="stop-buttons" role="group" aria-label="Configured stops">
    {#each stops as stop (stop.stop_id)}
      <button
        type="button"
        class="stop-button"
        class:active={selectedStopId === stop.stop_id}
        data-nav
        aria-pressed={selectedStopId === stop.stop_id}
        onclick={() => onSelect(stop.stop_id)}
      >
        {stop.name}
      </button>
    {:else}
      <span class="empty">No stops configured</span>
    {/each}
  </div>
</section>

<style>
  .stop-selector {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 68px;
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

  .stop-buttons {
    display: flex;
    gap: 8px;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .stop-buttons::-webkit-scrollbar {
    display: none;
  }

  .stop-button {
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

  .stop-button.active {
    border-color: #7dd3fc;
    background: #123247;
    color: #e0f5ff;
  }

  .empty {
    color: var(--color-muted);
    font-size: 0.9rem;
  }
</style>
