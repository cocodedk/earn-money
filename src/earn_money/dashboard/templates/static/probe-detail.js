// Right-panel renderer. Read-only over window.probeState. Calls
// window.getTurnStatus() + window.formatTurnStatus() for header text.
// Uses textContent for every LLM-controlled string — no DOM-write
// sinks (enforced by tests/dashboard/test_probe_static_assets.py).

(function () {
  const KNOWN_HEADINGS = [
    "=== Rules of Engagement ===",
    "=== Session State ===",
    "=== Available actions ===",
  ];

  // Splits a prompt into { _intro, "=== Heading ===": body, ... }.
  // Only known whitelist headings are treated as boundaries; unknown
  // === lines stay inside the current section. Returns null if no
  // whitelisted heading matched (prompt format drifted).
  window.splitPromptSections = function splitPromptSections(prompt, known) {
    const lines = (prompt || "").split("\n");
    const sections = { _intro: "" };
    let current = "_intro";
    let matched = false;
    for (const line of lines) {
      if (known.includes(line.trim())) {
        current = line.trim();
        sections[current] = "";
        matched = true;
      } else {
        sections[current] = sections[current]
          ? sections[current] + "\n" + line
          : line;
      }
    }
    return matched ? sections : null;
  };

  window.computeDelta = function computeDelta(prevPrompt, currPrompt, known) {
    const prev = window.splitPromptSections(prevPrompt, known);
    const curr = window.splitPromptSections(currPrompt, known);
    if (!prev || !curr) {
      return { couldNotCompute: true, body: currPrompt || "" };
    }
    const out = [];
    for (const key of Object.keys(curr)) {
      if (key === "_intro") continue;
      if (curr[key] !== prev[key]) {
        out.push(key + "\n" + curr[key]);
      }
    }
    return { couldNotCompute: false, body: out.join("\n") };
  };

  function _clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function _el(tag, className, text) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function _renderHeader(panel, turn, turnNum) {
    const status = window.getTurnStatus(turn);
    const statusText = window.formatTurnStatus(status);
    const lastAttempt = turn.attempts[turn.attempts.length - 1] || {};
    const header = _el("div", "probe-detail-header");
    header.appendChild(_el("span", "", "TURN " + turnNum));
    header.appendChild(_el("span", "", " · "));
    header.appendChild(_el("span", "", lastAttempt.model || "?"));
    header.appendChild(_el("span", "", " · "));
    header.appendChild(_el("span", "", statusText));
    if (turn.attempts.length > 1) {
      header.appendChild(_el("span", "probe-detail-retry-badge", "↻ retried"));
    }
    if (!window.probeState.followLatest) {
      const btn = _el("button", "probe-detail-follow-latest", "↓ follow latest");
      btn.addEventListener("click", () => window.setFollowLatest(true));
      header.appendChild(btn);
    }
    panel.appendChild(header);
  }

  function _renderTabs(panel) {
    const tabs = _el("div", "probe-detail-tabs");
    for (const name of ["delta", "full"]) {
      const cls = "probe-detail-tab" +
        (window.probeState.activeTab === name ? " is-active" : "");
      const btn = _el("button", cls, name);
      btn.addEventListener("click", () => window.setActiveTab(name));
      tabs.appendChild(btn);
    }
    panel.appendChild(tabs);
  }

  function _renderPrompt(panel, turn, turnNum) {
    const turns = window.probeState.turns;
    const prevNum = Math.max(0, ...Object.keys(turns).map(Number).filter((n) => n < turnNum));
    const prevTurn = turns[prevNum];
    const tab = window.probeState.activeTab;
    let labelText = null;
    let body;
    if (tab === "delta" && prevTurn) {
      const d = window.computeDelta(prevTurn.prompt, turn.prompt, KNOWN_HEADINGS);
      body = d.body;
      if (d.couldNotCompute) labelText = "could not compute delta";
    } else if (tab === "delta") {
      labelText = "first turn — no delta";
      body = turn.prompt;
    } else {
      body = (turn.system ? turn.system + "\n\n" : "") + (turn.prompt || "");
    }
    if (labelText) {
      panel.appendChild(_el("div", "probe-detail-delta-label", labelText));
    }
    panel.appendChild(_el("pre", "probe-detail-prompt", body));
  }

  function _renderAttempts(panel, turn) {
    const wrap = _el("div", "probe-detail-attempts");
    for (const a of turn.attempts) {
      const failed = a.parseOutcome === "failed";
      const card = _el("div", "probe-attempt-card" + (failed ? " is-failed" : ""));
      const rfTxt = a.used_response_format ? "with response_format" : "without response_format";
      card.appendChild(_el("div", "probe-attempt-card-header",
        "Attempt #" + a.attempt + " · " + rfTxt));
      card.appendChild(_el("pre", "probe-attempt-card-response", a.raw || ""));
      let statusTxt;
      if (a.parseOutcome === "ok") statusTxt = "✓ parsed";
      else if (failed) statusTxt = "⚠ parse failed: " + (a.parseError || "");
      else statusTxt = "… pending";
      card.appendChild(_el("div", "probe-attempt-card-status", statusTxt));
      wrap.appendChild(card);
    }
    panel.appendChild(wrap);
  }

  window.renderDetailPanel = function renderDetailPanel() {
    const panel = document.getElementById("probe-detail");
    if (!panel) return;
    _clear(panel);
    if (window.probeState.runError) {
      panel.appendChild(_el("div", "probe-detail-runerror",
        "Probe error: " + window.probeState.runError));
    }
    const turnNum = window.probeState.selectedTurn;
    const turn = turnNum != null ? window.probeState.turns[turnNum] : null;
    if (!turn) {
      panel.appendChild(_el("div", "probe-detail-header", "Waiting for first turn…"));
      return;
    }
    _renderHeader(panel, turn, turnNum);
    _renderTabs(panel);
    _renderPrompt(panel, turn, turnNum);
    _renderAttempts(panel, turn);
  };
})();
