<script lang="ts">
  import { activeView, setView, VIEWS, viewLabels } from '../lib/navigation'
</script>

<header class="top-nav">
  <div class="brand" aria-label="RMG-Watcher">
    <span class="brand-mark">RMG-Watcher</span>
  </div>

  <nav class="view-switcher" aria-label="Views">
    {#each VIEWS as view (view)}
      <button
        type="button"
        class="nav-button"
        class:active={$activeView === view}
        data-nav
        aria-current={$activeView === view ? 'page' : undefined}
        onclick={() => setView(view)}
      >
        {viewLabels[view]}
      </button>
    {/each}
  </nav>
</header>

<style>
  .top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 72px;
    padding: 8px 12px;
    border-bottom: 1px solid #263241;
    background: linear-gradient(180deg, #141b23 0%, #10161d 100%);
  }

  .brand {
    display: flex;
    align-items: baseline;
    gap: 10px;
    min-width: 0;
  }

  .brand-mark {
    padding: 4px 8px;
    border-radius: 6px;
    background: var(--color-accent);
    color: #04150a;
    font-size: 1rem;
    font-weight: 800;
    letter-spacing: 0.06em;
  }

  .view-switcher {
    display: flex;
    gap: 8px;
  }

  .nav-button {
    min-width: 104px;
    min-height: var(--tap-target);
    padding: 0 16px;
    border: 1px solid #2d3a49;
    border-radius: var(--radius);
    background: var(--color-surface);
    color: var(--color-text);
    font-weight: 700;
    letter-spacing: 0.01em;
    cursor: pointer;
  }

  .nav-button.active {
    border-color: var(--color-accent);
    background: #123d25;
    color: #d9ffe7;
    box-shadow: inset 0 -3px 0 var(--color-accent);
  }

  @media (max-width: 640px) {
    .brand-mark {
      font-size: 0.8rem;
      letter-spacing: 0;
    }

    .nav-button {
      min-width: 84px;
      padding: 0 10px;
    }
  }
</style>
