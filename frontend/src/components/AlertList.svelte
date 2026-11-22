<script lang="ts">
  import type { ServiceAlert } from '../lib/types'

  interface Props {
    alerts: ServiceAlert[]
    loading: boolean
    error: string | null
    stopNames: Map<string, string>
  }

  let { alerts, loading, error, stopNames }: Props = $props()

  function severityClass(severity: string): string {
    const value = severity.toUpperCase()
    if (value.includes('SEVERE') || value.includes('CRITICAL')) return 'severe'
    if (value.includes('WARNING') || value.includes('MODERATE')) return 'warning'
    return 'info'
  }
</script>

<section class="alerts" aria-label="Service alerts" aria-busy={loading}>
  <header class="alerts-header">
    <div>
      <h2>Service alerts</h2>
      <p>Disruptions near your stops</p>
    </div>
    {#if alerts.length > 0}
      <span class="count">{alerts.length} active</span>
    {/if}
  </header>

  {#if error}
    <p class="state error" role="status">{error}</p>
  {:else if loading}
    <p class="state" role="status">Loading service alerts…</p>
  {:else if alerts.length === 0}
    <p class="state" role="status">No service alerts right now.</p>
  {:else}
    <ol class="alert-list">
      {#each alerts as alert (alert.code)}
        <li class="alert-row {severityClass(alert.severity)}">
          <span class="severity">{severityClass(alert.severity)}</span>
          <div class="alert-body">
            <strong>{alert.header}</strong>
            {#if alert.description}
              <p>{alert.description}</p>
            {/if}
            <span class="alert-stop">
              {alert.stop_id ? (stopNames.get(alert.stop_id) ?? alert.stop_id) : 'Network'}
            </span>
          </div>
          {#if alert.url}
            <a
              class="alert-link"
              href={alert.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="More information"
            >
              ↗
            </a>
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  .alerts {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    min-height: 0;
    overflow-y: auto;
  }

  .alerts-header {
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

  .alerts-header p {
    margin: 2px 0 0;
    color: var(--color-muted);
    font-size: 0.82rem;
  }

  .count {
    color: var(--color-muted);
    font-size: 0.8rem;
  }

  .alert-list {
    display: grid;
    gap: 8px;
    margin: 0;
    padding: 0 0 8px;
    list-style: none;
  }

  .alert-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px;
    border: 1px solid #263241;
    border-left: 4px solid #7dd3fc;
    border-radius: 10px;
    background: var(--color-surface);
  }

  .alert-row.warning {
    border-left-color: var(--color-warning);
  }

  .alert-row.severe {
    border-left-color: var(--color-danger);
  }

  .severity {
    flex: 0 0 auto;
    padding: 3px 8px;
    border-radius: 999px;
    background: #123247;
    color: #d9f1ff;
    font-size: 0.7rem;
    font-weight: 800;
    text-transform: uppercase;
  }

  .alert-row.warning .severity {
    background: #4a3410;
    color: #ffd58a;
  }

  .alert-row.severe .severity {
    background: #4b1616;
    color: #ffb4b4;
  }

  .alert-body {
    min-width: 0;
    flex: 1;
  }

  .alert-body p {
    margin: 4px 0;
    color: var(--color-muted);
    font-size: 0.86rem;
  }

  .alert-stop {
    color: var(--color-muted);
    font-size: 0.76rem;
  }

  .alert-link {
    flex: 0 0 auto;
    min-width: 44px;
    min-height: 44px;
    display: grid;
    place-items: center;
    color: #bde9ff;
    font-size: 1.2rem;
    text-decoration: none;
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
</style>
