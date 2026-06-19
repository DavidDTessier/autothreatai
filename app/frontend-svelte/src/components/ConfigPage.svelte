<script>
  import { AGENT_CONFIG } from '../lib/agents.js';
  import { createEventDispatcher } from 'svelte';
  import { updateProviderConfig, updateAgentProviderConfig } from '../lib/api.js';

  export let providers = [];
  export let selectedProviderId = '';
  let selectedAgentId = '';
  let isLocal = false;

  // Editable fields for the selected provider
  let apiKey = '';
  let baseUrl = '';
  let defaultModel = '';
  let enabled = true;
  let isSaving = false;
  let saveMessage = '';

  const dispatch = createEventDispatcher();

  // Watch for provider changes to populate edit fields
  $: {
    const p = providers.find(p => p.id === selectedProviderId);
    if (p) {
      isLocal = p.id === 'local';
      apiKey = p.api_key ?? '';
      baseUrl = p.base_url ?? '';
      defaultModel = p.default_model ?? '';
      enabled = p.enabled ?? true;
    }
    // Optional: if an agent is selected, you could load agent‑specific defaults here.
    // For now the UI shows the global provider values; the save request includes the agent.
  }

  async function handleSave() {
    if (!selectedProviderId) return;
    isSaving = true;
    saveMessage = '';
    try {
      let result;
        if (selectedAgentId) {
          result = await updateAgentProviderConfig({
            agent_id: selectedAgentId,
            provider_id: selectedProviderId,
            api_key: apiKey,
            base_url: baseUrl,
            default_model: defaultModel,
            enabled: enabled
          });
        } else {
          result = await updateProviderConfig({
            provider_id: selectedProviderId,
            api_key: apiKey,
            base_url: baseUrl,
            default_model: defaultModel,
            enabled: enabled
          });
        }
      // Notify parent that config changed
      dispatch('configSaved', result);
      saveMessage = 'Saved!';
      setTimeout(() => dispatch('close'), 300);
    } catch (e) {
      saveMessage = e.message || 'Save failed';
    } finally {
      isSaving = false;
    }
  }

  function handleCancel() {
    dispatch('close');
  }
</script>

<div class="config-overlay">
  <div class="config-panel">
    <h2>Settings</h2>

      <div class="field">
        <label for="agent-select">Agent</label>
        <select id="agent-select" bind:value={selectedAgentId}>
          {#each AGENT_CONFIG as a}
            <option value={a.id}>{a.name}</option>
          {/each}
        </select>
      </div>

    <div class="field">
      <label for="provider-select">Provider</label>
      <select id="provider-select" bind:value={selectedProviderId}>
        {#each providers as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </div>

    {#if selectedProviderId}
      <div class="field">
        <label for="api-key">API Key {#if isLocal}<span class="optional">(optional)</span>{/if}</label>
        <input id="api-key" type="password" bind:value={apiKey} placeholder="API key" />
      </div>

      <div class="field">
        <label for="base-url">Base URL {#if !isLocal}<span class="optional">(optional)</span>{/if}</label>
        <input id="base-url" type="text" bind:value={baseUrl} placeholder="e.g. http://localhost:11434" />
      </div>

      <div class="field">
        <label for="default-model">Default Model</label>
        <input id="default-model" type="text" bind:value={defaultModel} placeholder="model-id" />
      </div>

      <div class="field checkbox">
        <label>
          <input type="checkbox" bind:checked={enabled} />
          <span>Enabled</span>
        </label>
      </div>
    {/if}

    <div class="btn-group">
      <button on:click={handleSave} disabled={isSaving || !selectedProviderId}>Save</button>
      <button on:click={handleCancel} disabled={isSaving}>Cancel</button>
    </div>

    {#if saveMessage}
      <p class="save-message">{saveMessage}</p>
    {/if}
  </div>
</div>

<style>
  .config-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .config-panel {
    background: #fff;
    padding: 1.5rem;
    border-radius: 8px;
    min-width: 350px;
    max-width: 500px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  }
  .field {
    margin-bottom: 1rem;
  }
  .field label {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: 500;
  }
  .field input, .field select {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
  }
  .checkbox label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .btn-group {
    display: flex;
    gap: 0.75rem;
    margin-top: 1rem;
  }
  .btn-group button {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-group button:first-child {
    background: #0066cc;
    color: #fff;
  }
  .btn-group button:last-child {
    background: #f0f0f0;
  }
  .save-message {
    margin-top: 0.75rem;
    font-size: 0.9rem;
  }
  .optional {
    font-weight: normal;
    color: #666;
    font-size: 0.85rem;
  }
</style>