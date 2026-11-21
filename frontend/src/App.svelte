<script lang="ts">
  import DepartureList from './components/DepartureList.svelte'
  import StatusBanner from './components/StatusBanner.svelte'
  import StopSelector from './components/StopSelector.svelte'
  import TopNavBar from './components/TopNavBar.svelte'
</script>

<div class="kiosk">
  <TopNavBar />
  <StopSelector />
  <StatusBanner />
  <main class="kiosk-content">
    <DepartureList />
  </main>
</div>

<style>
  .kiosk {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .kiosk-content {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }
</style>
