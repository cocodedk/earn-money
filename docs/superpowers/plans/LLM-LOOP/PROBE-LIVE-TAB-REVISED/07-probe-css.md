### File 7: `static/probe.css` (NEW — live monitoring styles)

```css
/* PROBE tab — live pentesting monitor */

#probe-panel {
    padding: 1rem;
}

#probe-form {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
    padding: 1rem;
    background: var(--surface-1);
    border-radius: 8px;
}

#probe-form input {
    flex: 1;
    padding: 0.5rem;
    background: var(--surface-2);
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 4px;
}

#probe-form input:focus {
    outline: none;
    border-color: var(--accent);
}

#probe-run-btn {
    padding: 0.5rem 1.5rem;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
}

#probe-run-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

#probe-status {
    margin-bottom: 1rem;
    color: var(--text-dim);
    font-size: 0.9rem;
}

/* Timeline */
#probe-timeline {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    max-height: calc(100vh - 200px);
    overflow-y: auto;
}

/* Turn cards */
.turn-card {
    padding: 1rem;
    background: var(--surface-1);
    border-left: 3px solid var(--accent);
    border-radius: 4px;
    animation: slideIn 0.3s ease;
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}

.turn-header {
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: var(--accent);
    font-size: 0.9rem;
}

.turn-action {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}

.tool-badge {
    padding: 0.2rem 0.5rem;
    background: var(--surface-2);
    border-radius: 3px;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text);
}

.tool-badge.tool-get { border-left: 3px solid #4caf50; }
.tool-badge.tool-post { border-left: 3px solid #ff9800; }
.tool-badge.tool-report_candidate { border-left: 3px solid #e91e63; }
.tool-badge.tool-stop { border-left: 3px solid #9e9e9e; }
.tool-badge.tool-unknown { border-left: 3px solid #f44336; }

.action-path {
    font-family: var(--font-mono);
    color: var(--text-dim);
    font-size: 0.85rem;
}

/* Policy decisions */
.policy-decision {
    padding: 0.3rem 0.5rem;
    border-radius: 3px;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
}

.policy-allow {
    background: rgba(76, 175, 80, 0.15);
    color: #4caf50;
}

.policy-deny {
    background: rgba(244, 67, 54, 0.15);
    color: #f44336;
}

/* Observation */
.turn-observation {
    font-family: var(--font-mono);
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
    color: var(--text-dim);
}

.status-ok { color: #4caf50; }
.status-err { color: #f44336; }

.body-excerpt {
    padding: 0.5rem;
    background: var(--surface-2);
    border-radius: 3px;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 100px;
    overflow-y: auto;
    color: var(--text-dim);
    margin-bottom: 0.5rem;
}

/* Findings */
.turn-findings {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 0.5rem;
}

.finding-badge {
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.8rem;
}

.finding-badge.candidate {
    background: rgba(255, 152, 0, 0.2);
    color: #ff9800;
}

.finding-badge.verified {
    background: rgba(233, 30, 99, 0.2);
    color: #e91e63;
}

/* Token usage */
.turn-tokens {
    font-size: 0.75rem;
    color: var(--text-dim);
    text-align: right;
}

/* Cards for findings and completion */
.finding-card,
.done-card,
.error-card {
    padding: 0.75rem;
    border-radius: 4px;
    animation: slideIn 0.3s ease;
}

.finding-card.verified {
    background: rgba(233, 30, 99, 0.1);
    border: 1px solid rgba(233, 30, 99, 0.3);
    color: #e91e63;
}

.done-card {
    background: rgba(76, 175, 80, 0.1);
    border: 1px solid rgba(76, 175, 80, 0.3);
    color: #4caf50;
    font-weight: 600;
}

.error-card {
    background: rgba(244, 67, 54, 0.1);
    border: 1px solid rgba(244, 67, 54, 0.3);
    color: #f44336;
}
```

