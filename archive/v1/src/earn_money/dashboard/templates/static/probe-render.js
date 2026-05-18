// Timeline renderer (left column). Read-only over window.probeState.
// Calls window.getTurnStatus() + window.formatTurnStatus() for badge
// text. Does NOT mutate state. All event-handling logic lives in
// probe-state.js (the reducer).

(function () {
  function _el(tag, className, text) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function _renderTurnCard(turnNum, turn) {
    const card = _el("article", "turn-card");
    card.dataset.turn = String(turnNum);
    if (turn.complete) card.classList.add("complete");

    const lastAttempt = turn.attempts[turn.attempts.length - 1] || {};
    const status = window.getTurnStatus(turn);
    const statusText = window.formatTurnStatus(status);

    const header = _el("header");
    header.appendChild(_el("span", "turn-num", "TURN " + turnNum));
    header.appendChild(_el("span", "model-id", lastAttempt.model || "?"));
    header.appendChild(_el("span", "status status-" + status, statusText));
    if (turn.attempts.length > 1) {
      header.appendChild(_el("span", "retry-badge", "↻"));
    }
    card.appendChild(header);

    if (lastAttempt.raw) {
      card.appendChild(_el("div", "slot slot-action",
        (lastAttempt.raw || "").slice(0, 200)));
    }
    if (turn.policyDecision) {
      const cls = turn.policyDecision.allowed ? "policy-ok" : "policy-deny";
      const txt = (turn.policyDecision.allowed ? "✓ " : "✗ ") +
        (turn.policyDecision.reason || "");
      card.appendChild(_el("div", "slot slot-policy " + cls, txt));
    }
    if (turn.observation) {
      const obs = turn.observation;
      card.appendChild(_el("div", "slot slot-obs",
        obs.status + " " + (obs.content_type || "") + "  " + (obs.url || "") +
        "\n" + (obs.body_excerpt || "")));
    }
    return card;
  }

  function _clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  // Build the timeline DOM from the current state. Click handler attaches
  // here so probe.js doesn't need to thread it through.
  window.renderTimeline = function renderTimeline() {
    const timeline = document.getElementById("probe-timeline");
    if (!timeline) return;
    _clear(timeline);

    const turnNums = Object.keys(window.probeState.turns)
      .map(Number)
      .sort((a, b) => a - b);

    for (const n of turnNums) {
      const card = _renderTurnCard(n, window.probeState.turns[n]);
      if (window.probeState.selectedTurn === n) {
        card.classList.add("is-selected");
      }
      card.addEventListener("click", () => window.setSelectedTurn(n));
      timeline.appendChild(card);
    }

    if (window.probeState.runError) {
      timeline.appendChild(_el("div", "timeline-banner error",
        "error · " + window.probeState.runError));
    }
  };
})();
