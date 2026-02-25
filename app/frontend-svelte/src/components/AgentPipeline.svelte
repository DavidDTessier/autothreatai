<script>
  import { AGENT_CONFIG } from '../lib/agents.js';

  export let statuses = {};
</script>

<section class="status-section">
  <h2>Pipeline Status</h2>
  <div class="agent-pipeline">
    {#each AGENT_CONFIG as agent, i}
      {#if i > 0}
        <div class="pipeline-arrow">→</div>
      {/if}
      <div
        class="agent-card"
        class:waiting={statuses[agent.id] === 'waiting' || statuses[agent.id] == null}
        class:active={statuses[agent.id] === 'active'}
        class:completed={statuses[agent.id] === 'completed'}
        class:error={statuses[agent.id] === 'error'}
      >
        <div class="agent-icon">{agent.icon}</div>
        <div class="agent-info">
          <div class="agent-name">{agent.name}</div>
          <div class="agent-status">
            {#if statuses[agent.id] === 'active'}
              Processing...
            {:else if statuses[agent.id] === 'completed'}
              Complete
            {:else if statuses[agent.id] === 'error'}
              Failed
            {:else}
              Waiting
            {/if}
          </div>
        </div>
        <div class="agent-indicator"></div>
      </div>
    {/each}
  </div>
</section>
