<script>
  import { get } from 'svelte/store';
  import { writable } from 'svelte/store';
  import Header from './components/Header.svelte';
  import InputSection from './components/InputSection.svelte';
  import AgentPipeline from './components/AgentPipeline.svelte';
  import ReportSection from './components/ReportSection.svelte';
  import {
    getConfig,
    createSession,
    uploadFile,
    deleteUploadedFile,
    streamQuery,
    getLatestPdf,
    getDownloadUrl,
  } from './lib/api.js';
  import {
    AGENT_SEQUENCE,
    NEXT_AGENT_IDS,
    getAgentIdFromAuthor,
  } from './lib/agents.js';
  import { markdownToSafeHtml } from './lib/sanitize.js';

  const CURRENT_USER_ID = 'web_user';

  /** Map technical error messages to short, user-friendly text. Preserve already-friendly messages. */
  function userFriendlyError(rawMessage) {
    if (!rawMessage || typeof rawMessage !== 'string') return 'Analysis failed. Please try again or choose a different model.';
    const s = rawMessage.trim();
    const msg = s.toLowerCase();
    const technical = /404|not_found|traceback|at line|exception|error:\s*\{|\.py"|connection refused|timeout|e\.g\.|status.*code/i;
    if (s.length <= 120 && !technical.test(s)) return s;
    if ((msg.includes('404') || msg.includes('not_found') || msg.includes('not found')) && (msg.includes('model') || msg.includes('models/')))
      return 'The selected model is not available. Please choose a different model from the dropdown.';
    if (msg.includes('404') || msg.includes('not_found') || msg.includes('not found'))
      return 'The requested resource was not found. Please try again.';
    if (msg.includes('403') || msg.includes('permission') || msg.includes('forbidden'))
      return 'Access was denied. Please check your API key or Vertex AI permissions.';
    if (msg.includes('401') || msg.includes('unauthorized') || msg.includes('invalid api key') || msg.includes('invalid_api_key'))
      return 'Invalid or missing API key. Please check your credentials.';
    if (msg.includes('429') || msg.includes('quota') || msg.includes('rate limit'))
      return 'Request limit reached. Please wait a moment and try again.';
    if (msg.includes('500') || msg.includes('503') || msg.includes('502'))
      return 'The analysis service is temporarily unavailable. Please try again later.';
    if (msg.includes('connect') || msg.includes('connection') || msg.includes('refused') || msg.includes('timeout') || msg.includes('unreachable'))
      return 'Unable to reach the analysis service. Please check that all services are running and try again.';
    if (msg.includes('model') && (msg.includes('not') || msg.includes('unsupported') || msg.includes('not found')))
      return 'The selected model is not available. Please choose a different model from the dropdown.';
    return 'Analysis failed. Please try again or choose a different model.';
  }

  let architectureText = '';
  let uploadedFile = null;
  let uploadedFileServerPath = null;
  let apiKey = '';
  let useVertex = false;
  let vertexProject = '';
  let vertexLocation = 'us-central1';
  let selectedModelId = '';
  let supportedModels = [];
  let vertexAvailable = true;
  let sessionId = null;

  getConfig().then((c) => {
    if (c) {
      supportedModels = c.supported_models || [];
      vertexAvailable = c.vertex_available !== false;
      if (c.default_model_id && !selectedModelId) selectedModelId = c.default_model_id;
    }
  });
  let abortController = null;
  let fullReport = '';
  let reportHtml = '';
  const initialStatuses = {
    orchestrator: 'waiting',
    parser: 'waiting',
    modeler: 'waiting',
    ai_modeler: 'waiting',
    builder: 'waiting',
    verifier: 'waiting',
  };
  const agentStatusesStore = writable(initialStatuses);
  let isAnalyzing = false;
  let canReset = false;
  let canDownload = false;
  let errorMessage = '';

  function resetAgentStatuses() {
    agentStatusesStore.set({ ...initialStatuses });
  }

  function setAgentStatus(agentId, status) {
    agentStatusesStore.update((s) => ({ ...s, [agentId]: status }));
  }

  function getAgentStatus(agentId) {
    return get(agentStatusesStore)[agentId];
  }

  /** Normalize ADK event (backend may send snake_case). */
  function normEvent(ev) {
    if (!ev) return ev;
    const author = ev.author ?? ev.Author;
    const finishReason = ev.finishReason ?? ev.finish_reason;
    const turnComplete = ev.turn_complete ?? ev.turnComplete;
    const partial = ev.partial;
    const actions = ev.actions ?? {};
    const toolCalls = actions.toolCalls ?? actions.tool_calls ?? [];
    return { author, finishReason, turnComplete, partial, actions: { ...actions, toolCalls }, content: ev.content };
  }

  function processStreamEvent(event) {
    if (event && typeof event.error === 'string') {
      errorMessage = userFriendlyError(event.error);
      AGENT_SEQUENCE.forEach((id) => {
        if (getAgentStatus(id) !== 'completed') setAgentStatus(id, 'error');
      });
      return;
    }
    const e = normEvent(event);
    const author = e?.author;
    if (author) {
      const agentId = getAgentIdFromAuthor(author);
      const finishReasons = ['STOP', 'DONE', 'MAX_TOKENS'];
      const isFinished =
        finishReasons.includes(e.finishReason) ||
        e.turnComplete === true ||
        (e.partial === false && e.content != null);
      if (typeof window !== 'undefined' && window.__DEBUG_PIPELINE) {
        console.log('[Pipeline] event author=', author, '->', agentId, isFinished ? 'complete' : 'active');
      }

      if (isFinished) {
        setAgentStatus(agentId, 'completed');
        if (agentId === 'modeler') setAgentStatus('ai_modeler', 'waiting');
        if (agentId === 'ai_modeler') setAgentStatus('modeler', 'waiting');
        const nextIds = NEXT_AGENT_IDS[agentId] || [];
        for (const nextId of nextIds) {
          const st = getAgentStatus(nextId);
          if (st !== 'completed' && st !== 'active') setAgentStatus(nextId, 'active');
        }
      } else {
        if (getAgentStatus(agentId) !== 'active' && getAgentStatus(agentId) !== 'completed') {
          setAgentStatus(agentId, 'active');
        }
      }
    }

    if (author && (String(author).includes('verification_loop') || String(author).includes('verification-loop'))) {
      if (getAgentStatus('builder') !== 'active' && getAgentStatus('builder') !== 'completed') {
        setAgentStatus('builder', 'active');
      }
    }

    const toolCalls = e?.actions?.toolCalls ?? [];
    for (const tc of toolCalls) {
      const name = tc.name ?? tc.function_call?.name;
      if (name?.includes('write_file') || name?.includes('convert_markdown')) {
        if (getAgentStatus('builder') !== 'active' && getAgentStatus('builder') !== 'completed') {
          setAgentStatus('builder', 'active');
        }
      }
      if ((name ?? '') === 'convert_markdown_to_pdf' && (tc.response ?? tc.function_response)) {
        const res = typeof tc.response === 'string' ? JSON.parse(tc.response) : tc.response ?? tc.function_response;
        if (res?.file_path?.endsWith('.pdf')) {
          // PDF path tracked server-side for download
        }
      }
    }

    if (event?.content) {
      let text = '';
      if (typeof event.content === 'string') text = event.content;
      else if (event.content.parts) {
        for (const p of event.content.parts) if (p.text) text += p.text;
      } else if (event.content.text) text = event.content.text;
      if (text) fullReport += text;
    }
  }

  async function handleStartAnalysis() {
    const text = architectureText.trim();
    if (!text && !uploadedFile) {
      errorMessage = 'Please enter an architecture description or upload a diagram';
      return;
    }

    const hasApiKey = apiKey.trim().length > 0;
    const hasVertex = vertexAvailable && useVertex && vertexProject.trim().length > 0 && vertexLocation.trim().length > 0;
    if (!hasApiKey && !hasVertex) {
      errorMessage = 'Credentials required: provide either a Google API key or Vertex AI (check Use Vertex AI and fill Project ID and Location).';
      return;
    }

    fullReport = '';
    reportHtml = '';
    errorMessage = '';
    resetAgentStatuses();
    isAnalyzing = true;
    canReset = false;
    canDownload = false;

    if (abortController) abortController.abort();
    abortController = new AbortController();
    const signal = abortController.signal;

    try {
      const session = await createSession();
      sessionId = session.session_id;
      if (!sessionId) throw new Error('No session ID');

      const messageParts = [];
      if (text) messageParts.push({ text });
      if (uploadedFile) {
        const fileData = await uploadFile(uploadedFile, signal);
        uploadedFileServerPath = fileData.serverFilename;
        messageParts.push({
          inlineData: { mimeType: fileData.mimeType, data: fileData.data },
        });
      }

      setAgentStatus('orchestrator', 'active');

      await streamQuery(
        {
          user_id: CURRENT_USER_ID,
          session_id: sessionId,
          message_parts: messageParts,
          api_key: apiKey.trim() || undefined,
          use_vertex: useVertex,
          vertex_project: vertexProject.trim() || undefined,
          vertex_location: vertexLocation.trim() || undefined,
          model_id: selectedModelId.trim() || undefined,
        },
        {
          signal,
          onChunk: (chunk) => {
            const event = chunk?.event ?? chunk?.data ?? chunk;
            processStreamEvent(event);
          },
        }
      );

      AGENT_SEQUENCE.forEach((id) => {
        const st = get(agentStatusesStore)[id];
        if (st === 'active' || st === 'completed') setAgentStatus(id, 'completed');
      });

      reportHtml = markdownToSafeHtml(fullReport);

      isAnalyzing = false;
      canReset = true;
      canDownload = true;
    } catch (err) {
      if (err.name === 'AbortError') return;
      errorMessage = userFriendlyError(err.message || 'Analysis failed');
      isAnalyzing = false;
      canReset = true;
    }
  }

  async function handleRemoveFile() {
    if (uploadedFileServerPath) {
      try {
        await deleteUploadedFile(uploadedFileServerPath);
      } catch (_) {}
      uploadedFileServerPath = null;
    }
    uploadedFile = null;
  }

  async function handleReset() {
    if (abortController) abortController.abort();
    sessionId = null;
    fullReport = '';
    reportHtml = '';
    errorMessage = '';
    resetAgentStatuses();
    architectureText = '';
    await handleRemoveFile();
    isAnalyzing = false;
    canReset = false;
    canDownload = false;
  }

  async function handleDownload() {
    try {
      const data = await getLatestPdf();
      if (data?.filename) {
        const url = getDownloadUrl(data.filename);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        return;
      }
    } catch (_) {}
    if (fullReport.trim()) {
      const blob = new Blob([fullReport], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `threat-model-report-${new Date().toISOString().split('T')[0]}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }
</script>

<div class="container">
  <Header />
  <div class="main-content">
    <InputSection
      bind:architectureText
      bind:uploadedFile
      bind:apiKey
      bind:useVertex
      bind:vertexProject
      bind:vertexLocation
      bind:selectedModelId
      {supportedModels}
      {vertexAvailable}
      {isAnalyzing}
      {canReset}
      onAnalyze={handleStartAnalysis}
      onReset={handleReset}
      onRemoveFile={handleRemoveFile}
    />
    <AgentPipeline statuses={$agentStatusesStore} />
    <ReportSection
      {fullReport}
      {reportHtml}
      {isAnalyzing}
      {errorMessage}
      {canDownload}
      onDownload={handleDownload}
    />
  </div>
</div>
