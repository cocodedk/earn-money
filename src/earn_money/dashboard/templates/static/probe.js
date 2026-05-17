// Dispatcher. No state access. Wires DOM events + EventSource into the
// reducer; registers a single onChange callback that triggers a render
// of both panels. probe-state.js is the only state writer.

(function () {
  const form = document.getElementById("probe-form");
  const runBtn = document.getElementById("probe-run");
  const local = { es: null, closed: false, run_id: null };

  function _renderAll() {
    if (window.renderTimeline) window.renderTimeline();
    if (window.renderDetailPanel) window.renderDetailPanel();
  }

  window.onChange(_renderAll);
  _renderAll();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (local.es) return;
    const body = serialiseForm(form);
    runBtn.disabled = true;
    local.closed = false;

    // Clear state via the reducer — only writer to state.turns / etc.
    window.probeReducer({ stage: "probe_start" });

    let res;
    try {
      res = await fetch("/api/probe/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (err) {
      window.probeReducer({ stage: "probe_error", message: "network error: " + err.message });
      runBtn.disabled = false;
      return;
    }
    if (!res.ok) {
      const ej = await res.json().catch(() => ({ error: res.statusText }));
      window.probeReducer({ stage: "probe_error", message: ej.error || "start failed" });
      runBtn.disabled = false;
      return;
    }
    const { run_id } = await res.json();
    local.run_id = run_id;
    _writeRunIdToHash(run_id);
    openStream(run_id);
  });

  // Page-reload survival. The dashboard process keeps a per-run event
  // history; a reload that lands here with `#run=<id>` reopens the SSE
  // stream and the server replays the full trace from seq 0. EventSource
  // also sets `Last-Event-ID` on subsequent reconnects, so dropped
  // connections resume without duplicating events.
  function _readRunIdFromHash() {
    const m = (location.hash || "").match(/(?:^|&)run=([0-9a-fA-F]{32})\b/);
    return m ? m[1] : null;
  }
  function _writeRunIdToHash(run_id) {
    const tail = "run=" + run_id;
    if (!location.hash) { location.hash = tail; return; }
    if (location.hash.indexOf("run=") >= 0) {
      location.hash = location.hash.replace(/run=[0-9a-fA-F]+/, tail);
    } else {
      location.hash = location.hash + "&" + tail;
    }
  }
  const _bootRunId = _readRunIdFromHash();
  if (_bootRunId) {
    local.run_id = _bootRunId;
    window.probeReducer({ stage: "probe_start" });
    runBtn.disabled = true;
    // Force-switch to the Probe tab. Without this a URL like
    // `#run=<id>` (no `tab=probe`) reattaches the stream but the
    // panel stays hidden behind the default Recon tab.
    document.querySelector('button.tab[data-tab="probe"]')?.click();
    openStream(_bootRunId);
  }

  function openStream(run_id) {
    const es = new EventSource("/api/probe/stream?run_id=" + encodeURIComponent(run_id));
    local.es = es;

    es.addEventListener("turn", (e) => {
      if (local.closed) return;
      window.probeReducer(JSON.parse(e.data));
    });
    // `finding` events: v1 doesn't render findings in the detail panel;
    // each turn's preceding `turn/complete` event already triggered the
    // final render via the reducer. No listener wired.
    es.addEventListener("done", () => {
      if (local.closed) return;
      local.closed = true;
      // The preceding `turn/complete` reducer event already updated the
      // final turn and fired onChange. `done` is a stream-lifecycle
      // signal only — close the EventSource + re-enable the form.
      es.close();
      local.es = null;
      runBtn.disabled = false;
    });
    es.addEventListener("probe_error", (e) => {
      if (local.closed) return;
      local.closed = true;
      window.probeReducer({ stage: "probe_error", ...JSON.parse(e.data) });
      es.close();
      local.es = null;
      runBtn.disabled = false;
    });
    es.onerror = () => {
      if (local.closed) return;
      local.closed = true;
      window.probeReducer({ stage: "probe_error", message: "stream connection lost" });
      es.close();
      local.es = null;
      runBtn.disabled = false;
    };
  }

  function serialiseForm(form) {
    const d = new FormData(form);
    const out = {};
    for (const [k, v] of d.entries()) if (v) out[k] = v;
    if (out.max_turns) out.max_turns = parseInt(out.max_turns, 10);
    return out;
  }
})();
