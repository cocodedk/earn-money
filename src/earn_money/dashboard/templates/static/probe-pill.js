// Header pill that surfaces "there is a probe running" from any tab.
// Polls /api/probe/current every 5s; clicking the pill navigates to
// `#tab=probe&run=<id>` which probe.js + tabs.js already handle.

(function () {
  const pill = document.getElementById("active-probe-pill");
  if (!pill) return;

  const labelEl  = pill.querySelector(".pill-label");
  const targetEl = pill.querySelector(".pill-target");
  const turnEl   = pill.querySelector(".pill-turn");

  function _hostFromUrl(url) {
    try { return new URL(url).host; } catch (_) { return url || ""; }
  }

  function _renderActive(meta) {
    pill.hidden = false;
    pill.dataset.state = meta.is_running ? "running" : "done";
    labelEl.textContent = meta.is_running ? "PROBE" : "PROBE · DONE";
    targetEl.textContent = _hostFromUrl(meta.base_url);
    // Pull the latest turn count from the live state when available;
    // otherwise leave the slot empty (avoid stale numbers).
    const maxTurn = (window.probeState && window.probeState.maxTurn) || 0;
    turnEl.textContent = maxTurn ? ("T" + maxTurn + "/" + (meta.max_turns || "?")) : "";
    pill.setAttribute("href", "#tab=probe&run=" + encodeURIComponent(meta.run_id));
  }

  function _renderIdle() {
    pill.hidden = true;
    pill.removeAttribute("data-state");
    pill.setAttribute("href", "#tab=probe");
  }

  async function _poll() {
    try {
      const res = await fetch("/api/probe/current");
      if (!res.ok) return _renderIdle();
      const meta = await res.json();
      if (!meta || !meta.run_id) return _renderIdle();
      _renderActive(meta);
    } catch (_) {
      _renderIdle();
    }
  }

  _poll();
  setInterval(_poll, 5000);
})();
