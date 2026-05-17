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
  // Boot sequence — async so we can discover an active run via the
  // `/api/probe/current` endpoint when the URL hash doesn't already
  // carry one. Three paths:
  //   1. `#run=<id>` in hash → attach to that run, force Probe tab
  //   2. `#tab=probe` only   → discover + attach if a probe is running
  //   3. neither              → no-op; the header pill (probe-pill.js)
  //      still shows the operator there's something to click
  async function _boot() {
    let runId = _readRunIdFromHash();
    let forceTab = !!runId;
    if (!runId && /(?:^#|&)tab=probe(?:&|$)/.test(location.hash || "")) {
      runId = await _discoverActiveRun();
    }
    if (!runId) return;
    local.run_id = runId;
    window.probeReducer({ stage: "probe_start" });
    runBtn.disabled = true;
    if (forceTab) {
      document.querySelector('button.tab[data-tab="probe"]')?.click();
    }
    openStream(runId);
  }

  async function _discoverActiveRun() {
    try {
      const res = await fetch("/api/probe/current");
      if (!res.ok) return null;
      const data = await res.json();
      return data && data.run_id ? data.run_id : null;
    } catch (_) { return null; }
  }
  _boot();

  function openStream(run_id) {
    const es = new EventSource("/api/probe/stream?run_id=" + encodeURIComponent(run_id));
    local.es = es;

    es.addEventListener("turn", (e) => {
      if (local.closed) return;
      window.probeReducer(JSON.parse(e.data));
    });
    // `meta` carries run config (base_url, target_kind, roe_profile,
    // platform, program, max_turns). The runner emits it as the
    // first history entry so replay always lands one even after
    // page reload, letting the form mirror what's actually running.
    es.addEventListener("meta", (e) => {
      if (local.closed) return;
      let meta;
      try { meta = JSON.parse(e.data); } catch (_) { return; }
      _populateFormFromMeta(meta);
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

  function _populateFormFromMeta(meta) {
    // The meta event is authoritative state for the currently-watched
    // run. Overwrite every field for which the server has a value;
    // null/empty payload values keep the placeholder visible. The
    // event fires once right after stream connect — well before the
    // operator has had time to type into the form — so there is no
    // realistic clobbering risk.
    const map = {
      base_url:    meta.base_url,
      target_kind: meta.target_kind,
      roe_profile: meta.roe_profile,
      max_turns:   meta.max_turns,
      platform:    meta.platform,
      program:     meta.program,
    };
    for (const name of Object.keys(map)) {
      const v = map[name];
      if (v === null || v === undefined || v === "") continue;
      const el = form.elements[name];
      if (el) el.value = v;
    }
  }

  function serialiseForm(form) {
    const d = new FormData(form);
    const out = {};
    for (const [k, v] of d.entries()) if (v) out[k] = v;
    if (out.max_turns) out.max_turns = parseInt(out.max_turns, 10);
    return out;
  }
})();
