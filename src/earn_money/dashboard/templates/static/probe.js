(function () {
  const form = document.getElementById("probe-form");
  const runBtn = document.getElementById("probe-run");
  const timeline = document.getElementById("probe-timeline");
  const state = { es: null, closed: false, run_id: null };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.es) return;
    const body = serialiseForm(form);
    runBtn.disabled = true;
    timeline.replaceChildren();
    state.closed = false;

    let res;
    try {
      res = await fetch("/api/probe/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (err) {
      ProbeRender.showError(timeline, { message: "network error: " + err.message, stage: "gate" });
      runBtn.disabled = false;
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }));
      ProbeRender.showError(timeline, { message: err.error || "start failed", stage: "gate" });
      runBtn.disabled = false;
      return;
    }
    const { run_id } = await res.json();
    state.run_id = run_id;
    openStream(run_id);
  });

  function openStream(run_id) {
    const es = new EventSource("/api/probe/stream?run_id=" + encodeURIComponent(run_id));
    state.es = es;

    es.addEventListener("turn", (e) => {
      if (state.closed) return;
      ProbeRender.appendOrUpdateTurnCard(timeline, JSON.parse(e.data));
    });
    es.addEventListener("finding", (e) => {
      if (state.closed) return;
      ProbeRender.appendFinding(timeline, JSON.parse(e.data));
    });
    es.addEventListener("done", (e) => {
      if (state.closed) return;
      state.closed = true;
      ProbeRender.markComplete(timeline, JSON.parse(e.data));
      es.close();
      state.es = null;
      runBtn.disabled = false;
    });
    es.addEventListener("probe_error", (e) => {
      if (state.closed) return;
      state.closed = true;
      const payload = JSON.parse(e.data);
      ProbeRender.showError(timeline, payload);
      es.close();
      state.es = null;
      runBtn.disabled = false;
    });
    es.onerror = () => {
      if (state.closed) return;
      state.closed = true;
      ProbeRender.showError(timeline, { message: "stream connection lost", stage: "runtime" });
      es.close();
      state.es = null;
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
