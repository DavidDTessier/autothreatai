// Agent name mapping from ADK agent names to UI IDs
const AGENT_MAPPING = {
    'threat_model_orchestrator': 'orchestrator',
    'architecture_parser_agent': 'parser',
    'threat_modeler_agent': 'modeler',
    'report_builder_agent': 'builder',
    'report_verifier_agent': 'verifier',
 
};

// Expected agent sequence for proactive status updates
const AGENT_SEQUENCE = ['orchestrator', 'parser', 'modeler', 'builder', 'verifier'];

// Use relative URLs to go through the FastAPI proxy
const API_BASE = '';
let currentSessionId = null;
let currentUserId = 'web_user';
let abortController = null;
let fullReport = '';
let pdfFilePath = null; // Store PDF file path when available
let agentStatuses = {}; // Track agent statuses

// DOM elements
const input = document.getElementById('architecture-input');
const analyzeBtn = document.getElementById('analyze-btn');
const resetBtn = document.getElementById('reset-btn');
const downloadBtn = document.getElementById('download-btn');
const reportContent = document.getElementById('report-content');
const diagramUpload = document.getElementById('diagram-upload');
const filePreview = document.getElementById('file-preview');
const fileName = document.getElementById('file-name');
const removeFileBtn = document.getElementById('remove-file');

// Store uploaded file
let uploadedFile = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    analyzeBtn.addEventListener('click', startAnalysis);
    resetBtn.addEventListener('click', resetAnalysis);
    downloadBtn.addEventListener('click', downloadReport);
    
    // File upload handlers
    diagramUpload.addEventListener('change', handleFileSelect);
    removeFileBtn.addEventListener('click', removeFile);
});

// Set agent status with more detailed messages - optimized for immediate updates
function setAgentStatus(agentId, status, message = null) {
    const agentCard = document.getElementById(`agent-${agentId}`);
    if (!agentCard) return;
    
    // Update immediately without delays for responsive UI
    // Remove all status classes
    agentCard.classList.remove('waiting', 'active', 'completed');
    
    // Add appropriate status class
    if (status === 'active') {
        agentCard.classList.add('active');
        const statusText = message || getAgentStatusMessage(agentId, 'active');
        const statusElement = agentCard.querySelector('.agent-status');
        if (statusElement) {
            statusElement.textContent = statusText;
        }
    } else if (status === 'completed') {
        agentCard.classList.add('completed');
        const statusText = message || getAgentStatusMessage(agentId, 'completed');
        const statusElement = agentCard.querySelector('.agent-status');
        if (statusElement) {
            statusElement.textContent = statusText;
        }
    } else {
        agentCard.classList.add('waiting');
        const statusElement = agentCard.querySelector('.agent-status');
        if (statusElement) {
            statusElement.textContent = 'Waiting';
        }
    }
    
    // Store status
    agentStatuses[agentId] = status;
}

// Get status message for agent
function getAgentStatusMessage(agentId, status) {
    const messages = {
        orchestrator: {
            active: 'Orchestrating workflow...',
            completed: 'Workflow complete'
        },
        parser: {
            active: 'Parsing architecture...',
            completed: 'Architecture parsed'
        },
        modeler: {
            active: 'Analyzing threats...',
            completed: 'Threats identified'
        },
        builder: {
            active: 'Building report...',
            completed: 'Report built'
        },
        verifier: {
            active: 'Verifying report...',
            completed: 'Report verified'
        }
    };
    
    return messages[agentId]?.[status] || (status === 'active' ? 'Processing...' : 'Complete');
}

// Reset all agents to waiting state
function resetAllAgents() {
    ['orchestrator', 'parser', 'modeler', 'builder', 'verifier'].forEach(agentId => {
        setAgentStatus(agentId, 'waiting');
        agentStatuses[agentId] = 'waiting';
    });
}

// Handle file selection
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        // Validate file type
        if (!file.type.startsWith('image/')) {
            alert('Please select an image file');
            diagramUpload.value = '';
            return;
        }
        
        // Validate file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
            alert('File size must be less than 10MB');
            diagramUpload.value = '';
            return;
        }
        
        uploadedFile = file;
        fileName.textContent = file.name;
        filePreview.style.display = 'flex';
    }
}

// Remove uploaded file
function removeFile() {
    uploadedFile = null;
    diagramUpload.value = '';
    filePreview.style.display = 'none';
}

// Convert file to base64
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            // Remove data URL prefix (e.g., "data:image/png;base64,")
            const base64 = reader.result.split(',')[1];
            resolve({
                data: base64,
                mimeType: file.type,
                displayName: file.name
            });
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

// Start analysis
async function startAnalysis() {
    const architectureText = input.value.trim();
    if (!architectureText && !uploadedFile) {
        alert('Please enter an architecture description or upload a diagram');
        return;
    }
    
    // Reset UI
    fullReport = '';
    reportContent.innerHTML = '<div class="placeholder"><div class="placeholder-icon spinning">⏳</div><div class="placeholder-text">Starting analysis... Your report will appear here once the workflow is complete.</div></div>';
    resetAllAgents();
    analyzeBtn.disabled = true;
    resetBtn.disabled = true;
    downloadBtn.disabled = true;
    
    // Cancel any existing request
    if (abortController) {
        abortController.abort();
    }
    abortController = new AbortController();
    
    try {
        // Step 1: Create a session
        console.log('Creating session...');
        const session = await createSession();
        console.log('Session created:', session);
        if (!session || !session.session_id) {
            throw new Error('Failed to create session: No session ID returned');
        }
        currentSessionId = session.session_id;
        console.log('Using session ID:', currentSessionId);
        
        // Step 2: Prepare message parts (text + optional image)
        const messageParts = [];
        
        if (architectureText) {
            messageParts.push({ text: architectureText });
        }
        
        if (uploadedFile) {
            console.log('Converting file to base64...');
            const fileData = await fileToBase64(uploadedFile);
            messageParts.push({
                inlineData: {
                    mimeType: fileData.mimeType,
                    data: fileData.data
                }
            });
            console.log('File converted, mimeType:', fileData.mimeType);
        }
        
        // Step 3: Start streaming query
        console.log('Starting stream query with', messageParts.length, 'parts...');
        await streamQuery(messageParts);
        
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Analysis cancelled');
            return;
        }
        console.error('Analysis error:', error);
        reportContent.innerHTML = `<div class="placeholder"><div class="placeholder-icon">❌</div><div class="placeholder-text">Error: ${error.message}</div></div>`;
        analyzeBtn.disabled = false;
        resetBtn.disabled = false;
    }
}

// Create a session with the orchestrator
async function createSession() {
    const response = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    });
    
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to create session: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    // Extract session_id from response (ADK returns 'id' field)
    const sessionId = data.id || data.session_id;
    if (!sessionId) {
        throw new Error('Session ID not found in response');
    }
    return {
        session_id: sessionId
    };
}

// Stream query to the orchestrator
async function streamQuery(messageParts) {
    const url = `${API_BASE}/api/query`;
    
    // Reduced logging for performance
    const DEBUG = false; // Set to true for debugging
    if (DEBUG) {
        console.log('Streaming query to:', url);
    }
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: currentUserId,
            session_id: currentSessionId,
            message_parts: messageParts
        }),
        signal: abortController.signal
    });
    
    if (DEBUG) {
        console.log('Response status:', response.status);
    }
    
    if (!response.ok) {
        const errorText = await response.text();
        console.error('Query failed:', response.status, errorText);
        throw new Error(`Query failed: ${response.status} - ${errorText}`);
    }
    
    if (!response.body) {
        throw new Error('Response body is null - server may not support streaming');
    }
    
    // Set orchestrator as active immediately
    setAgentStatus('orchestrator', 'active');
    agentStatuses['orchestrator'] = 'active';
    
    // Read the stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    // Show processing placeholder - don't clear, just show status
    reportContent.innerHTML = '<div class="placeholder"><div class="placeholder-icon spinning">⏳</div><div class="placeholder-text">Processing... Your report will appear here once the workflow is complete.</div></div>';
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                // Mark all active agents as completed
                ['orchestrator', 'parser', 'modeler', 'builder', 'verifier'].forEach(agentId => {
                    if (agentStatuses[agentId] === 'active' || agentStatuses[agentId] === 'completed') {
                        setAgentStatus(agentId, 'completed');
                    }
                });
                
                // Now display the complete report after workflow is done
                updateReportDisplay();
                
                analyzeBtn.disabled = false;
                resetBtn.disabled = false;
                downloadBtn.disabled = false;
                
                // Trigger celebration animation
                triggerCelebration();
                    break;
            }
            
            // Decode chunk
            buffer += decoder.decode(value, { stream: true });
            
            // Process events immediately - don't wait for \n\n
            // Process all complete lines in buffer (lines ending with \n)
            let newlineIndex;
            while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
                const line = buffer.substring(0, newlineIndex).trim();
                buffer = buffer.substring(newlineIndex + 1);
                
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.substring(6);
                        if (jsonStr) {
                            const data = JSON.parse(jsonStr);
                            // Process events immediately - no delays
                            processStreamEvent(data);
                        }
                    } catch (e) {
                        // Not valid JSON yet, might be incomplete - skip for now
                        // Will be retried when more data arrives
                    }
                }
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Stream cancelled');
            return;
        }
        throw error;
    }
}

// Process stream events - optimized for immediate status updates
function processStreamEvent(event) {
    // Prioritize status updates for immediate visual feedback
    if (event.author) {
        let agentId = AGENT_MAPPING[event.author];
        
        // If not found in mapping, try fuzzy matching on author name
        if (!agentId) {
            const authorLower = event.author.toLowerCase();
            if (authorLower.includes('parser') || authorLower.includes('architecture')) {
                agentId = 'parser';
            } else if (authorLower.includes('modeler') || (authorLower.includes('threat') && !authorLower.includes('orchestr'))) {
                agentId = 'modeler';
            } else if (authorLower.includes('builder') || authorLower.includes('content') || (authorLower.includes('report') && !authorLower.includes('verif'))) {
                agentId = 'builder';
            } else if (authorLower.includes('verifier') || authorLower.includes('verification') || authorLower.includes('escalation')) {
                agentId = 'verifier';
            } else if (authorLower.includes('orchestrator') || authorLower.includes('orchestrat')) {
                agentId = 'orchestrator';
            } else {
                agentId = event.author.toLowerCase();
            }
        }
        
        if (agentId && document.getElementById(`agent-${agentId}`)) {
            // Check completion FIRST for immediate visual feedback (before checking active)
            if (event.finishReason === 'STOP' || event.finishReason === 'DONE' || event.finishReason === 'MAX_TOKENS') {
                // Agent has finished - mark as completed immediately (no delay)
                setAgentStatus(agentId, 'completed');
                agentStatuses[agentId] = 'completed';
                
                // Proactively mark next agent as starting (if we know the sequence)
                const currentIndex = AGENT_SEQUENCE.indexOf(agentId);
                if (currentIndex >= 0 && currentIndex < AGENT_SEQUENCE.length - 1) {
                    const nextAgentId = AGENT_SEQUENCE[currentIndex + 1];
                    // Only mark as active if not already completed
                    if (agentStatuses[nextAgentId] !== 'completed' && agentStatuses[nextAgentId] !== 'active') {
                        // Mark next agent as "starting" - will become active when it emits events
                        setAgentStatus(nextAgentId, 'active');
                        agentStatuses[nextAgentId] = 'active';
                    }
                }
            } else {
                // Agent is active - mark immediately when we see their first event
                if (agentStatuses[agentId] !== 'active' && agentStatuses[agentId] !== 'completed') {
                    setAgentStatus(agentId, 'active');
                    agentStatuses[agentId] = 'active';
                }
            }
        }
    }
    
    // Detect verification_loop events - it starts with builder, so mark builder active immediately
    if (event.author && (event.author.includes('verification_loop') || event.author.includes('verification-loop'))) {
        // Verification loop's first sub-agent is builder - mark it active immediately
        if (agentStatuses['builder'] !== 'active' && agentStatuses['builder'] !== 'completed') {
            setAgentStatus('builder', 'active');
            agentStatuses['builder'] = 'active';
        }
    }
    
    // Detect agent transitions from tool calls - builder uses write_file and convert_markdown_to_pdf
    if (event.actions && event.actions.toolCalls) {
        for (const toolCall of event.actions.toolCalls) {
            if (toolCall.name && (toolCall.name.includes('write_file') || toolCall.name.includes('convert_markdown'))) {
                // These tools are used by builder - proactively mark builder as active
                if (agentStatuses['builder'] !== 'active' && agentStatuses['builder'] !== 'completed') {
                    setAgentStatus('builder', 'active');
                    agentStatuses['builder'] = 'active';
                }
            }
        }
    }
    
    // Check for artifact delta (PDF file creation)
    if (event.actions && event.actions.artifactDelta) {
        const artifacts = event.actions.artifactDelta;
        for (const [filename, artifact] of Object.entries(artifacts)) {
            if (filename.endsWith('.pdf')) {
                // PDF artifact created - store the path
                pdfFilePath = artifact.filePath || filename;
                console.log('PDF file created:', pdfFilePath);
            }
        }
    }
    
    // Process content - accumulate but don't display until workflow is complete
    if (event.content) {
        let text = '';
        
        // Handle different content formats
        if (typeof event.content === 'string') {
            text = event.content;
        } else if (event.content.parts) {
            // ADK format with parts
            for (const part of event.content.parts) {
                if (part.text) {
                    text += part.text;
                }
            }
        } else if (event.content.text) {
            text = event.content.text;
        }
        
        if (text) {
            fullReport += text;
            // Don't call updateReportDisplay() here - wait until workflow is complete
        }
    }
    
    // Check for tool calls that might indicate PDF creation
    if (event.actions && event.actions.toolCalls) {
        for (const toolCall of event.actions.toolCalls) {
            if (toolCall.name === 'convert_markdown_to_pdf' && toolCall.response) {
                const response = typeof toolCall.response === 'string' 
                    ? JSON.parse(toolCall.response) 
                    : toolCall.response;
                if (response.file_path && response.file_path.endsWith('.pdf')) {
                    pdfFilePath = response.file_path;
                    console.log('PDF file path from tool call:', pdfFilePath);
                }
            }
        }
    }
}

// Update report display
function updateReportDisplay() {
    if (!fullReport.trim()) {
        // Show placeholder if no content yet
        reportContent.innerHTML = '<div class="placeholder"><div class="placeholder-icon spinning">⏳</div><div class="placeholder-text">Processing... Your report will appear here once the workflow is complete.</div></div>';
        return;
    }
    
    // Convert markdown to HTML (simple implementation)
    let html = fullReport;
    
    // Basic markdown to HTML conversion
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
    html = html.replace(/`(.*?)`/gim, '<code>$1</code>');
    html = html.replace(/\n\n/gim, '</p><p>');
    html = '<p>' + html + '</p>';
    
    reportContent.innerHTML = html;
    
    // Auto-scroll to bottom
    reportContent.scrollTop = reportContent.scrollHeight;
}

// Download report as PDF
async function downloadReport() {
    try {
        // First try to get the latest PDF
        const response = await fetch(`${API_BASE}/api/reports/latest-pdf`);
        
        if (response.ok) {
            const data = await response.json();
            const filename = data.filename;
            
            // Download the PDF file
            const downloadUrl = `${API_BASE}/api/reports/download/${filename}`;
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            console.log('Downloaded PDF:', filename);
            return;
        } else if (response.status === 404) {
            // No PDF found, fallback to markdown download
            console.warn('PDF not found, downloading markdown instead');
            downloadReportAsMarkdown();
        } else {
            throw new Error(`Failed to get PDF: ${response.status}`);
        }
    } catch (error) {
        console.error('Error downloading PDF:', error);
        // Fallback to markdown download
        downloadReportAsMarkdown();
    }
}

// Fallback: Download report as markdown
function downloadReportAsMarkdown() {
    if (!fullReport.trim()) {
        alert('No report to download');
        return;
    }
    
    // Create blob and download
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

// Trigger celebration animation with balloons
function triggerCelebration() {
    const container = document.getElementById('balloon-container');
    if (!container) return;
    
    // Clear any existing balloons
    container.innerHTML = '';
    
    // Balloon colors
    const colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#f9ca24', '#f0932b', '#eb4d4b', '#6c5ce7', '#a29bfe'];
    
    // Create 15-20 balloons
    const balloonCount = 18;
    const balloons = [];
    
    for (let i = 0; i < balloonCount; i++) {
        const balloon = document.createElement('div');
        balloon.className = 'balloon';
        balloon.style.left = `${Math.random() * 100}%`;
        balloon.style.animationDelay = `${Math.random() * 0.5}s`;
        balloon.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        
        // Add balloon string
        const string = document.createElement('div');
        string.className = 'balloon-string';
        balloon.appendChild(string);
        
        container.appendChild(balloon);
        balloons.push(balloon);
    }
    
    // Pop balloons sequentially after they've risen a bit
    setTimeout(() => {
        balloons.forEach((balloon, index) => {
            setTimeout(() => {
                balloon.classList.add('pop');
                // Remove balloon after pop animation
                setTimeout(() => {
                    balloon.remove();
                }, 500);
            }, index * 100 + 2000); // Stagger pops
        });
    }, 1000);
}

// Reset analysis
function resetAnalysis() {
    if (abortController) {
        abortController.abort();
    }
    
    currentSessionId = null;
    fullReport = '';
    pdfFilePath = null;
    agentStatuses = {};
    input.value = '';
    removeFile(); // Clear uploaded file
    
    // Clear balloons
    const container = document.getElementById('balloon-container');
    if (container) {
        container.innerHTML = '';
    }
    
    reportContent.innerHTML = '<div class="placeholder"><div class="placeholder-icon">📄</div><div class="placeholder-text">Your security threat report will appear here...</div></div>';
    resetAllAgents();
    analyzeBtn.disabled = false;
    resetBtn.disabled = true;
    downloadBtn.disabled = true;
}
