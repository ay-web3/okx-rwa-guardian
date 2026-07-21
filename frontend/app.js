const BASE_URL = 'http://127.0.0.1:8001';
const AGENT_LOGS_URL = `${BASE_URL}/agent-logs?limit=10`;

const elements = {
    queryBtn: document.getElementById('query-api-btn'),
    apiAsset: document.getElementById('api-asset'),
    apiLat: document.getElementById('api-lat'),
    apiLon: document.getElementById('api-lon'),
    apiSig: document.getElementById('api-sig'),
    apiResponseCode: document.getElementById('api-response-code'),
    aiAnalysisText: document.getElementById('ai-analysis-text')
};

// Append text to the AI Terminal
function appendToTerminal(text, type = 'normal') {
    const lines = text.split('\n');
    let html = '';
    for (const line of lines) {
        if (!line.trim()) continue;
        let className = type === 'critical' ? 'error' : (type === 'warning' ? 'warning' : '');
        let formattedLine = line;
        
        // Format AI Reasoning prefix
        if (line.includes('AI decision:')) {
            formattedLine = line.replace('AI decision:', '<span style="color: var(--neon-amber); font-weight: bold;">[AI CHAIN OF THOUGHT]</span>');
        }
        
        html += `<div class="${className}">> ${formattedLine}</div>`;
    }
    elements.aiAnalysisText.innerHTML += html;
    elements.aiAnalysisText.scrollTop = elements.aiAnalysisText.scrollHeight;
}

// Poll backend for the multi-agent reasoning logs
async function fetchAgentLogs() {
    try {
        const response = await fetch(AGENT_LOGS_URL);
        if (response.ok) {
            const logs = await response.json();
            elements.aiAnalysisText.innerHTML = '';
            if (logs.length === 0) {
                appendToTerminal('> Multi-agent swarm initializing...', 'normal');
                appendToTerminal('> Standing by for Oracle queries...', 'normal');
                return;
            }
            logs.forEach(log => {
                const sender = log.sender || 'System';
                const summary = log.summary || '';
                let type = 'normal';
                if (summary.includes('CRITICAL') || summary.includes('PAUSE') || summary.includes('🚨')) type = 'critical';
                else if (summary.includes('⚠️') || summary.includes('REJECTED')) type = 'warning';
                appendToTerminal(`[${sender}] ${summary}`, type);
            });
        }
    } catch (err) {
        console.error('Failed to fetch agent logs:', err);
    }
}

// Poll every 2 seconds
setInterval(fetchAgentLogs, 2000);
fetchAgentLogs();

// Handle API Submission
elements.queryBtn.addEventListener('click', async () => {
    elements.queryBtn.disabled = true;
    const originalText = elements.queryBtn.innerText;
    elements.queryBtn.innerText = 'PROCESSING REQUEST...';
    
    const endpointPath = document.getElementById('api-endpoint').value;
    elements.apiResponseCode.style.color = "var(--text-muted)";
    elements.apiResponseCode.innerText = `Initiating POST request to ${endpointPath}...\nWaiting for AI Swarm consensus...`;

    const payload = {
        asset_name: elements.apiAsset.value,
        lat: parseFloat(elements.apiLat.value),
        lon: parseFloat(elements.apiLon.value)
    };

    const headers = {
        'Content-Type': 'application/json'
    };

    const signature = elements.apiSig.value.trim();
    if (signature) {
        headers['X-OKX-Payment-Signature'] = signature;
    }

    try {
        const response = await fetch(`${BASE_URL}${endpointPath}`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.status === 402) {
            // Payment Required
            elements.apiResponseCode.style.color = "var(--status-red)";
            elements.apiResponseCode.innerText = `// HTTP 402 PAYMENT REQUIRED\n\n${JSON.stringify(data, null, 2)}`;
            appendToTerminal(`[Gatekeeper] Request blocked. Missing or invalid OKX Nano-Payment Signature.`, 'critical');
        } else if (response.ok) {
            // Success
            elements.apiResponseCode.style.color = "var(--neon-green)";
            elements.apiResponseCode.innerText = `// HTTP 200 OK - ORACLE CONSENSUS REACHED\n\n${JSON.stringify(data, null, 2)}`;
        } else {
            // Other Errors
            elements.apiResponseCode.style.color = "var(--status-red)";
            elements.apiResponseCode.innerText = `// HTTP ${response.status} ERROR\n\n${JSON.stringify(data, null, 2)}`;
        }
    } catch (err) {
        elements.apiResponseCode.style.color = "var(--status-red)";
        elements.apiResponseCode.innerText = `// NETWORK ERROR\n\n${err.message}`;
    } finally {
        elements.queryBtn.disabled = false;
        elements.queryBtn.innerText = originalText;
    }
});