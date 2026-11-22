<script lang="ts">
  import type { Stop, TransferRisk } from '../lib/types'

  interface Props {
    risks: TransferRisk[]
    stops: Stop[]
    loading: boolean
  }

  let { risks, stops, loading }: Props = $props()

  const stopNames = $derived(new Map(stops.map((stop) => [stop.stop_id, stop.name])))
  const atRiskCount = $derived(risks.filter((risk) => risk.at_risk).length)
  const visibleRisks = $derived(risks.slice(0, 12))

  function stopName(stopId: string, preferred: string | null): string {
    if (preferred) return preferred
    const known = stopNames.get(stopId) ?? stopNames.get(knownId(stopId))
    if (known) return known
    if (stopId.toLowerCase() === 'hbf') return 'Darmstadt Hbf'
    if (stopId.toLowerCase() === 'luisenplatz') return 'Darmstadt Luisenplatz'
    return stopId.split(':').at(-1) ?? stopId
  }

  function knownId(stopId: string): string {
    if (stopId.includes('4736')) return 'de-amarillo-bw_de:06411:4736'
    if (stopId.includes('4734')) return 'de-DELFI_de:06411:4734'
    return stopId
  }

  function routeLabel(routeId: string): string {
    return routeId.replace(/^route[-_]?/i, '') || routeId
  }

  function formatSlack(seconds: number): string {
    const absolute = Math.abs(Math.round(seconds))
    if (absolute < 60) return `${absolute}s`
    const minutes = Math.floor(absolute / 60)
    const rest = absolute % 60
    return rest === 0 ? `${minutes} min` : `${minutes} min ${rest}s`
  }

  function slackText(risk: TransferRisk): string {
    if (risk.projected_slack_seconds === 0) return 'No slack'
    const label = formatSlack(risk.projected_slack_seconds)
    return risk.at_risk ? `${label} short` : `${label} spare`
  }
</script>

<section class="transfer-risks" aria-label="Transfer risks" aria-busy={loading}>
  <header class="risk-header">
    <div>
      <h2>Transfer risks</h2>
      <p>Connections ranked by remaining slack</p>
    </div>
    <span class="risk-count" class:alert={atRiskCount > 0}>
      {atRiskCount} at risk
    </span>
  </header>

  {#if loading && risks.length === 0}
    <p class="state" role="status">Loading transfer risks…</p>
  {:else if risks.length === 0}
    <p class="state" role="status">No transfer connections detected.</p>
  {:else}
    <ol class="risk-rows">
      {#each visibleRisks as risk, index (index)}
        <li class="risk-row" class:at-risk={risk.at_risk}>
          <span class="risk-status">{risk.at_risk ? 'At risk' : 'OK'}</span>

          <span class="transfer">
            <span class="route-chip">
              {risk.inbound_route_name ?? routeLabel(risk.inbound_route_id)}
            </span>
            <span class="arrow" aria-hidden="true">→</span>
            <span class="route-chip">
              {risk.outbound_route_name ?? routeLabel(risk.outbound_route_id)}
            </span>
          </span>

          <span class="risk-stop">{stopName(risk.stop_id, risk.stop_name)}</span>
          <span class="risk-slack">{slackText(risk)}</span>
        </li>
      {/each}
    </ol>

    {#if risks.length > visibleRisks.length}
      <p class="more">Showing the {visibleRisks.length} most urgent connections.</p>
    {/if}
  {/if}
</section>

<style>
  .transfer-risks {
    display: flex;
    flex-direction: column;
    gap: 10px;
    height: 100%;
    min-height: 0;
    overflow-y: auto;
  }

  .risk-header {
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

  .risk-header p {
    margin: 2px 0 0;
    color: var(--color-muted);
    font-size: 0.82rem;
  }

  .risk-count {
    flex: 0 0 auto;
    padding: 5px 10px;
    border-radius: 999px;
    background: #123d25;
    color: #b9f6ce;
    font-size: 0.78rem;
    font-weight: 800;
    white-space: nowrap;
  }

  .risk-count.alert {
    background: #4b1616;
    color: #ffb4b4;
  }

  .risk-rows {
    display: grid;
    gap: 6px;
    margin: 0;
    padding: 0 0 8px;
    list-style: none;
  }

  .risk-row {
    display: grid;
    grid-template-columns: 88px minmax(0, 1fr) minmax(0, 1.2fr) auto;
    align-items: center;
    gap: 12px;
    min-height: 58px;
    padding: 6px 12px;
    border: 1px solid #263241;
    border-left: 4px solid var(--color-accent);
    border-radius: 10px;
    background: var(--color-surface);
  }

  .risk-row.at-risk {
    border-left-color: var(--color-danger);
  }

  .risk-status {
    color: #b9f6ce;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .risk-row.at-risk .risk-status {
    color: #ffb4b4;
  }

  .transfer {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .route-chip {
    display: grid;
    place-items: center;
    min-width: 40px;
    height: 34px;
    padding: 0 8px;
    border-radius: 6px;
    background: #e8edf2;
    color: #0b0f14;
    font-weight: 800;
  }

  .arrow {
    color: var(--color-muted);
    font-size: 1.1rem;
  }

  .risk-stop {
    overflow: hidden;
    color: var(--color-text);
    font-size: 0.9rem;
    font-weight: 600;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .risk-slack {
    color: var(--color-muted);
    font-size: 0.84rem;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .risk-row.at-risk .risk-slack {
    color: #ffc18f;
    font-weight: 700;
  }

  .more {
    margin: 0;
    color: var(--color-muted);
    font-size: 0.76rem;
    text-align: center;
  }

  .state {
    margin: 8px 0;
    padding: 22px 16px;
    border: 1px dashed #2d3a49;
    border-radius: 10px;
    color: var(--color-muted);
    text-align: center;
  }

  @media (max-width: 600px) {
    .risk-row {
      grid-template-columns: 76px minmax(0, 1fr) auto;
    }

    .risk-stop {
      display: none;
    }
  }
</style>
