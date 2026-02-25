<script>
  export let fullReport = '';
  export let reportHtml = '';
  export let isAnalyzing = false;
  export let errorMessage = '';
  export let canDownload = false;
  export let onDownload = () => {};

  let contentEl;

  $: if (contentEl && reportHtml) {
    contentEl.scrollTop = contentEl.scrollHeight;
  }
</script>

<section class="report-section">
  <div class="report-header">
    <h2>Security Threat Report</h2>
    <div class="report-actions">
      <button
        class="btn btn-download"
        disabled={!canDownload}
        on:click={onDownload}
      >
        <span class="btn-icon">📥</span>
        <span class="btn-text">Download PDF Report</span>
      </button>
    </div>
  </div>
  <div
    class="report-content"
    bind:this={contentEl}
    role="region"
    aria-label="Report content"
  >
    {#if errorMessage}
      <div class="placeholder placeholder-error">
        <div class="placeholder-icon" aria-hidden="true">❌</div>
        <p class="placeholder-text placeholder-error-text">{errorMessage}</p>
      </div>
    {:else if isAnalyzing && !fullReport}
      <div class="placeholder">
        <div class="placeholder-icon spinning">⏳</div>
        <div class="placeholder-text">Starting analysis... Your report will appear here once the workflow is complete.</div>
      </div>
    {:else if isAnalyzing}
      <div class="placeholder">
        <div class="placeholder-icon spinning">⏳</div>
        <div class="placeholder-text">Processing... Your report will appear here once the workflow is complete.</div>
      </div>
    {:else if reportHtml}
      {@html reportHtml}
    {:else}
      <div class="placeholder">
        <div class="placeholder-icon">📄</div>
        <div class="placeholder-text">Your security threat report will appear here...</div>
      </div>
    {/if}
  </div>
</section>
