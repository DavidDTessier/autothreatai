<script>
  export let architectureText = "";
  export let uploadedFile = null;
  export let isAnalyzing = false;
  export let canReset = false;
  export let apiKey = "";
  export let useVertex = false;
  export let vertexProject = "";
  export let vertexLocation = "us-central1";
  export let selectedProviderId = "";
  /** @type {{ id: string; name: string; default_model?: string; enabled: boolean }[]} */
  export let providers = [];
  export let vertexAvailable = true;
  /** @type {() => void} */
  export let onAnalyze = () => {};
  /** @type {() => void} */
  export let onReset = () => {};
  /** @type {() => void} */
  export let onRemoveFile = () => {};

  let fileInput;
  let fileName = "";
  let fileSizeText = "";
  const MAX_SIZE_MB = 10;
  const MAX_BYTES = MAX_SIZE_MB * 1024 * 1024;

  $: hasFile = !!uploadedFile;
  $: isLocalSelected = selectedProviderId?.startsWith("local");
  $: uploadLabelText = hasFile
    ? "Change Diagram"
    : "Upload Reference Diagram (Optional)";
  $: if (!uploadedFile) {
    fileName = "";
    fileSizeText = "";
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      alert("Please select an image file");
      if (fileInput) fileInput.value = "";
      return;
    }
    if (file.size > MAX_BYTES) {
      alert(`File size must be less than ${MAX_SIZE_MB}MB`);
      if (fileInput) fileInput.value = "";
      return;
    }
    uploadedFile = file;
    fileName = file.name;
    fileSizeText = (file.size / (1024 * 1024)).toFixed(2) + " MB";
    if (fileInput) fileInput.value = "";
  }

  function triggerFileInput() {
    fileInput?.click();
  }

  function removeFile() {
    uploadedFile = null;
    fileName = "";
    fileSizeText = "";
    if (fileInput) fileInput.value = "";
    onRemoveFile();
  }

  function updateFile() {
    fileInput?.click();
  }
</script>

<section class="input-section">
  <div class="input-container">
    <label for="architecture-input">Enter Architecture Description:</label>
    <textarea
      id="architecture-input"
      bind:value={architectureText}
      placeholder="Describe your system architecture, components, data flows, and security requirements..."
      rows="8"
      disabled={isAnalyzing}
    ></textarea>

    <div class="credentials-section">
      <p class="credentials-heading">
        {#if isLocalSelected}
          Credentials (optional for local models)
        {:else}
          Credentials (required — provide Google API key or Vertex AI)
        {/if}
      </p>
      {#if providers.length > 0}
        <div class="credentials-row">
          <label for="provider-select-svelte">Provider</label>
          <select
            id="provider-select-svelte"
            bind:value={selectedProviderId}
            disabled={isAnalyzing}
            class="provider-select"
          >
            {#each providers as p}
              <option value={p.id}>{p.name}</option>
            {/each}
          </select>
        </div>
      {/if}
      <div class="credentials-row">
        <label for="api-key-svelte"
          >Google API Key{#if isLocalSelected}
            <span class="optional-badge">(Optional)</span>{/if}</label
        >
        <input
          id="api-key-svelte"
          type="password"
          bind:value={apiKey}
          placeholder={isLocalSelected
            ? "Not needed for local models"
            : "Google/Gemini API key"}
          autocomplete="off"
          disabled={isAnalyzing}
        />
      </div>
      {#if vertexAvailable}
        <div class="credentials-row vertex-toggle">
          <label class="checkbox-label">
            <input
              type="checkbox"
              bind:checked={useVertex}
              disabled={isAnalyzing}
            />
            <span>Use Vertex AI</span>
          </label>
        </div>
      {/if}
      {#if vertexAvailable && useVertex}
        <div class="vertex-fields">
          <div class="credentials-row">
            <label for="vertex-project-svelte">Vertex Project ID</label>
            <input
              id="vertex-project-svelte"
              type="text"
              bind:value={vertexProject}
              placeholder="e.g. my-gcp-project"
              autocomplete="off"
              disabled={isAnalyzing}
            />
          </div>
          <div class="credentials-row">
            <label for="vertex-location-svelte">Vertex Location</label>
            <input
              id="vertex-location-svelte"
              type="text"
              bind:value={vertexLocation}
              placeholder="e.g. us-central1 or global"
              autocomplete="off"
              disabled={isAnalyzing}
            />
          </div>
        </div>
      {/if}
    </div>

    <div class="file-upload-section">
      <button
        type="button"
        class="file-upload-label"
        class:file-selected={hasFile}
        on:click={triggerFileInput}
        on:keydown={(e) => e.key === "Enter" && triggerFileInput()}
      >
        <span class="file-upload-icon">📎</span>
        <span class="file-upload-text">{uploadLabelText}</span>
      </button>
      <input
        bind:this={fileInput}
        type="file"
        accept="image/*,.png,.jpg,.jpeg,.gif,.webp"
        on:change={handleFileChange}
        style="display: none;"
        aria-label="Upload diagram"
      />
      {#if hasFile}
        <div class="file-preview">
          <div class="file-info">
            <span class="file-icon">📄</span>
            <div class="file-details">
              <span class="file-name">{fileName}</span>
              <span class="file-size">{fileSizeText}</span>
            </div>
          </div>
          <div class="file-actions">
            <button
              type="button"
              class="btn-update-file"
              title="Replace file"
              on:click={updateFile}>🔄</button
            >
            <button
              type="button"
              class="btn-remove-file"
              title="Remove file"
              on:click={removeFile}>×</button
            >
          </div>
        </div>
      {/if}
    </div>

    <div class="button-group">
      <button
        class="btn btn-primary"
        disabled={isAnalyzing}
        on:click={onAnalyze}
      >
        <span class="btn-icon">🚀</span>
        <span class="btn-text">Start Analysis</span>
      </button>
      <button class="btn btn-secondary" disabled={!canReset} on:click={onReset}>
        <span class="btn-icon">🔄</span>
        <span class="btn-text">Reset</span>
      </button>
    </div>
  </div>
</section>
