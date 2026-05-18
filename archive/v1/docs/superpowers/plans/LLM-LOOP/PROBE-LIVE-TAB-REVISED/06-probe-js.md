### File 6: `static/probe.js` (NEW — live monitoring frontend)

```javascript
// PROBE tab — live monitoring for pentesting loop

class ProbeMonitor {
    constructor() {
        this.form = document.getElementById('probe-form');
        this.timeline = document.getElementById('probe-timeline');
        this.runBtn = document.getElementById('probe-run-btn');
        this.urlInput = document.getElementById('probe-url');
        this.roeInput = document.getElementById('probe-roe');
        this.statusEl = document.getElementById('probe-status');
        
        this.eventSource = null;
        this.turns = [];
        this.bindEvents();
    }
    
    bindEvents() {
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.startProbe();
        });
    }
    
    async startProbe() {
        const baseUrl = this.urlInput.value.trim();
        const roeProfile = this.roeInput.value.trim() || 'roe/local-lab.yaml';
        
        if (!baseUrl) {
            this.showError('Please enter a target URL');
            return;
        }
        
        // Disable UI
        this.runBtn.disabled = true;
        this.statusEl.textContent = 'Starting probe...';
        this.timeline.textContent = '';  // Clear previous
        this.turns = [];
        
        try {
            const resp = await fetch('/api/probe/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    base_url: baseUrl,
                    roe_profile: roeProfile,
                }),
            });
            
            if (!resp.ok) {
                const err = await resp.json();
                this.showError(err.error || 'Failed to start probe');
                return;
            }
            
            const { run_id } = await resp.json();
            this.statusEl.textContent = `Running (${run_id})...`;
            this.connectStream();
            
        } catch (err) {
            this.showError(`Connection failed: ${err.message}`);
            this.runBtn.disabled = false;
        }
    }
    
    connectStream() {
        this.eventSource = new EventSource('/api/probe/stream');
        
        this.eventSource.addEventListener('turn', (e) => {
            const msg = JSON.parse(e.data);
            const data = msg.data;
            this.turns.push(data);
            this.renderTurn(data);
        });
        
        this.eventSource.addEventListener('finding', (e) => {
            const msg = JSON.parse(e.data);
            this.renderFinding(msg.data);
        });
        
        this.eventSource.addEventListener('done', (e) => {
            const msg = JSON.parse(e.data);
            this.renderDone(msg.data);
            this.close();
        });
        
        this.eventSource.addEventListener('error', (e) => {
            const msg = JSON.parse(e.data);
            this.showError(msg.data.message || 'Stream error');
            this.close();
        });
        
        this.eventSource.onerror = () => {
            this.showError('Connection to probe stream lost');
            this.close();
        };
    }
    
    renderTurn(data) {
        const card = document.createElement('div');
        card.className = 'turn-card';
        
        // Turn header
        const header = document.createElement('div');
        header.className = 'turn-header';
        header.textContent = `Turn ${data.turn} · ${data.task_type} · ${data.model}`;
        card.appendChild(header);
        
        // Action
        const action = document.createElement('div');
        action.className = 'turn-action';
        const actionData = data.parsed_action || {};
        action.innerHTML = `
            <span class="tool-badge tool-${actionData.tool || 'unknown'}">${
                (actionData.tool || 'unknown').toUpperCase()
            }</span>
            <span class="action-path">${actionData.args?.path || ''}</span>
        `;
        card.appendChild(action);
        
        // Policy decision
        const policy = document.createElement('div');
        policy.className = `policy-decision policy-${
            data.policy_decision?.allowed ? 'allow' : 'deny'
        }`;
        policy.textContent = data.policy_decision?.allowed
            ? `✓ ALLOWED — ${data.policy_decision.reason}`
            : `✗ DENIED — ${data.policy_decision.reason}`;
        card.appendChild(policy);
        
        // Observation
        if (data.observation) {
            const obs = document.createElement('div');
            obs.className = 'turn-observation';
            const status = data.observation.status || '???';
            const statusClass = status < 400 ? 'status-ok' : 'status-err';
            obs.textContent = `← ${status} ${data.observation.url || ''}`;
            card.appendChild(obs);
            
            // Body excerpt
            if (data.observation.body_excerpt) {
                const excerpt = document.createElement('pre');
                excerpt.className = 'body-excerpt';
                excerpt.textContent = data.observation.body_excerpt.substring(0, 300);
                card.appendChild(excerpt);
            }
        }
        
        // Findings
        if (data.candidates?.length > 0 || data.verified?.length > 0) {
            const findings = document.createElement('div');
            findings.className = 'turn-findings';
            
            data.candidates.forEach(f => {
                const badge = document.createElement('span');
                badge.className = 'finding-badge candidate';
                badge.textContent = `🔍 ${f.type || 'candidate'}`;
                findings.appendChild(badge);
            });
            
            data.verified.forEach(f => {
                const badge = document.createElement('span');
                badge.className = 'finding-badge verified';
                badge.textContent = `✓ ${f.type || 'verified'}`;
                findings.appendChild(badge);
            });
            
            card.appendChild(findings);
        }
        
        // Token usage
        if (data.token_usage) {
            const tokens = document.createElement('div');
            tokens.className = 'turn-tokens';
            tokens.textContent = `~${data.token_usage.estimated_tokens || 0} tokens`;
            card.appendChild(tokens);
        }
        
        this.timeline.appendChild(card);
        card.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    
    renderFinding(data) {
        const card = document.createElement('div');
        card.className = 'finding-card verified';
        card.textContent = `✓ FINDING: ${data.type} — ${data.path || ''}`;
        this.timeline.appendChild(card);
        card.scrollIntoView({ behavior: 'smooth' });
    }
    
    renderDone(data) {
        const card = document.createElement('div');
        card.className = 'done-card';
        card.textContent = `Probe complete · ${data.stop_reason} · ${this.turns.length} turns`;
        this.timeline.appendChild(card);
        this.statusEl.textContent = `Done: ${data.stop_reason}`;
    }
    
    showError(msg) {
        const card = document.createElement('div');
        card.className = 'error-card';
        card.textContent = `⚠ ${msg}`;
        this.timeline.appendChild(card);
        this.statusEl.textContent = msg;
    }
    
    close() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.runBtn.disabled = false;
    }
}

// Initialize on PROBE tab
document.addEventListener('DOMContentLoaded', () => {
    new ProbeMonitor();
});
```

