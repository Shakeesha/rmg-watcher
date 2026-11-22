<script lang="ts">
  import { onMount } from 'svelte'
  import type { HealthResponse } from '../lib/types'
  import {
    MILLISECONDS_PER_SECOND,
    MINUTES_PER_HOUR,
    SECONDS_PER_MINUTE,
  } from '../lib/constants'

  interface Props {
    health: HealthResponse | null
    error: string | null
    online: boolean
    lastUpdated: Date | null
    warning: string | null
  }

  let { health, error, online, lastUpdated, warning }: Props = $props()

  let now = $state(Date.now())

  onMount(() => {
    const timer = window.setInterval(() => {
      now = Date.now()
    }, 10_000)
    return () => window.clearInterval(timer)
  })

  const ageSeconds = $derived(
    lastUpdated === null
      ? null
      : Math.max(
          0,
          Math.floor(
            (now - lastUpdated.getTime()) / MILLISECONDS_PER_SECOND,
          ),
        ),
  )

  const stale = $derived(ageSeconds !== null && ageSeconds > 90)

  const tone = $derived.by(() => {
    if (!online) return 'offline'
    if (error) return 'error'
    if (health !== null && !health.database_ok) return 'error'
    if (warning) return 'warning'
    if (stale) return 'stale'
    if (health !== null && health.status !== 'ok') return 'warning'
    return 'ok'
  })

  const message = $derived.by(() => {
    if (!online) return 'Offline — showing the last known data'
    if (error) return 'Connection problem — retrying automatically'
    if (health === null) return 'Connecting to the transit service…'
    if (!health.database_ok) return 'Database unavailable — retrying automatically'
    if (warning) return warning
    if (stale) return 'Data is stale — waiting for the next refresh'
    if (health.status !== 'ok') return 'Pipeline degraded — last run needs attention'
    if (health.mock_mode) return 'Mock data — pipeline is running without the live API'
    return 'Live data'
  })

  function formatAge(seconds: number | null): string {
    if (seconds === null) return 'not loaded yet'
    if (seconds < 10) return 'just now'
    if (seconds < SECONDS_PER_MINUTE) return `${seconds}s ago`
    const minutes = Math.floor(seconds / SECONDS_PER_MINUTE)
    if (minutes < MINUTES_PER_HOUR) return `${minutes}m ago`
    const hours = Math.floor(minutes / MINUTES_PER_HOUR)
    return `${hours}h ago`
  }
</script>

<div class={`status-banner ${tone}`} role="status" aria-live="polite">
  <span class="status-dot" aria-hidden="true"></span>
  <span class="status-message">{message}</span>

  <span class="status-meta">
    {#if health?.mock_mode}
      <span class="chip mock">MOCK</span>
    {/if}
    {#if health !== null}
      <span class="version">v{health.version}</span>
    {/if}
    <span class="updated">Updated {formatAge(ageSeconds)}</span>
  </span>
</div>

<style>
  .status-banner {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 38px;
    padding: 5px 12px;
    border-bottom: 1px solid #1f2a36;
    background: #0d1319;
    font-size: 0.82rem;
  }

  .status-dot {
    flex: 0 0 auto;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--color-muted);
  }

  .status-banner.ok .status-dot {
    background: var(--color-accent);
    box-shadow: 0 0 0 3px rgb(53 196 107 / 18%);
  }

  .status-banner.warning .status-dot,
  .status-banner.stale .status-dot {
    background: var(--color-warning);
  }

  .status-banner.error .status-dot,
  .status-banner.offline .status-dot {
    background: var(--color-danger);
  }

  .status-banner.warning,
  .status-banner.stale {
    color: #ffdca8;
  }

  .status-banner.error,
  .status-banner.offline {
    color: #ffc9c9;
  }

  .status-message {
    min-width: 0;
    overflow: hidden;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .status-meta {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    color: var(--color-muted);
    white-space: nowrap;
  }

  .chip {
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.08em;
  }

  .chip.mock {
    background: #4a3410;
    color: #ffd58a;
  }

  .version {
    font-variant-numeric: tabular-nums;
  }

  @media (max-width: 640px) {
    .version {
      display: none;
    }
  }
</style>
