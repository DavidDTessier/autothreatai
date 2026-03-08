<script>
  import { getAgentConfig, PIPELINE_STEPS } from '../lib/agents.js';

  export let statuses = {};

  /** Force Svelte to track statuses and re-render when any value changes. */
  $: statusKey = statuses && typeof statuses === 'object' ? JSON.stringify(statuses) : '';

  /** Render one agent card. */
  function cardClasses(id) {
    const s = statuses[id];
    return {
      waiting: s === 'waiting' || s == null,
      active: s === 'active',
      completed: s === 'completed',
      error: s === 'error',
    };
  }
  function statusLabel(id) {
    const s = statuses[id];
    if (s === 'active') return 'Processing...';
    if (s === 'completed') return 'Complete';
    if (s === 'error') return 'Failed';
    return 'Waiting';
  }
</script>

<section class="status-section">
  <h2>Pipeline Status</h2>
  <div class="agent-pipeline">
    {#key statusKey}
    {#each PIPELINE_STEPS as step, i}
      {#if i > 0}
        <div class="pipeline-arrow">→</div>
      {/if}
      {#if Array.isArray(step)}
        <div class="pipeline-branch">
          {#each step as id}
            {@const agent = getAgentConfig(id)}
            {#if agent}
              <div
                class="agent-card"
                class:waiting={cardClasses(id).waiting}
                class:active={cardClasses(id).active}
                class:completed={cardClasses(id).completed}
                class:error={cardClasses(id).error}
              >
                <div class="agent-icon">{agent.icon}</div>
                <div class="agent-info">
                  <div class="agent-name">{agent.name}</div>
                  <div class="agent-status">{statusLabel(id)}</div>
                </div>
                <div class="agent-indicator"></div>
              </div>
            {/if}
          {/each}
        </div>
      {:else}
        {@const agent = getAgentConfig(step)}
        {#if agent}
          <div
            class="agent-card"
            class:waiting={cardClasses(step).waiting}
            class:active={cardClasses(step).active}
            class:completed={cardClasses(step).completed}
            class:error={cardClasses(step).error}
          >
            <div class="agent-icon">{agent.icon}</div>
            <div class="agent-info">
              <div class="agent-name">{agent.name}</div>
              <div class="agent-status">{statusLabel(step)}</div>
            </div>
            <div class="agent-indicator"></div>
          </div>
        {/if}
      {/if}
    {/each}
    {/key}
  </div>
</section>
