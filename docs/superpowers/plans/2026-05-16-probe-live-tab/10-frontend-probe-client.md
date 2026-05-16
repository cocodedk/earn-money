# Task 10 — `probe.js` (form + SSE) + `probe-render.js` (DOM renderers)

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/09-frontend-probe-client.md`

**Files:**
- Create: `src/earn_money/dashboard/templates/static/probe.js`
- Create: `src/earn_money/dashboard/templates/static/probe-render.js`

`probe.js` drives the form submit and the `EventSource`. `probe-render.js` owns every DOM mutation (no `innerHTML` anywhere) and exposes `window.ProbeRender` for the driver to call. No unit tests for these (the spec calls them out as manual-smoke only); behaviour is verified by the SSE-frame tests added in Task 7.

- [ ] **Step 1: Create `probe-render.js`**

Create `src/earn_money/dashboard/templates/static/probe-render.js` with the spec's exact content:

```js
(function () {
  function $card(timeline, turn) {
    let card = timeline.querySelector(`[data-turn="${turn}"]`);
    if (card) return card;
    card = document.createElement("article");
    card.className = "turn-card";
    card.dataset.turn = String(turn);
    card.append(
      buildHeader(turn),
      buildSlot("action"),
      buildSlot("policy"),
      buildSlot("obs"),
      buildSlot("findings"),
    );
    timeline.append(card);
    return card;
  }

  function buildSlot(name) {
    const el = document.createElement("div");
    el.className = "slot slot-" + name;
    return el;
  }

  function buildHeader(turn) {
    const h = document.createElement("header");
    const num = document.createElement("span");
    num.className = "turn-num";
    num.textContent = "TURN " + turn;
    const model = document.createElement("span");
    model.className = "model-id";
    const tokens = document.createElement("span");
    tokens.className = "tokens";
    h.append(num, model, tokens);
    return h;
  }

  function appendOrUpdateTurnCard(timeline, data) {
    const card = $card(timeline, data.turn);
    const header = card.querySelector("header");
    if (data.stage === "action_pending") {
      header.querySelector(".model-id").textContent = data.model || "?";
      header.querySelector(".tokens").textContent = "~" + (data.estimated_tokens || 0) + "t";
      card.querySelector(".slot-action").textContent = data.raw_excerpt || "";
    } else if (data.stage === "action_parsed") {
      const slot = card.querySelector(".slot-action");
      slot.textContent = JSON.stringify(data.action);
      if (data.parse_recovered) slot.dataset.recovered = "true";
    } else if (data.stage === "policy") {
      const slot = card.querySelector(".slot-policy");
      slot.textContent = (data.policy.allowed ? "✓ " : "✗ ") + data.policy.reason;
      slot.className = "slot slot-policy " + (data.policy.allowed ? "policy-ok" : "policy-deny");
    } else if (data.stage === "observation") {
      const slot = card.querySelector(".slot-obs");
      slot.textContent = `${data.obs.status} ${data.obs.content_type}  ${data.obs.url}\n${data.obs.body_excerpt}`;
    } else if (data.stage === "complete") {
      card.classList.add("complete", "outcome-" + data.outcome);
    }
  }

  function appendFinding(timeline, data) {
    const card = $card(timeline, data.turn);
    const row = document.createElement("div");
    row.className = "finding-row finding-" + data.kind;
    row.textContent = `[${data.kind}:${data.type}] ${data.path || data.target || "?"}`;
    card.querySelector(".slot-findings").append(row);
  }

  function markComplete(timeline, data) {
    const banner = document.createElement("div");
    banner.className = "timeline-banner";
    banner.textContent = `done · ${data.turns} turns · stop=${data.stop_reason} · candidates=${data.candidates_count} verified=${data.verified_count}`;
    timeline.append(banner);
  }

  function showError(timeline, data) {
    const banner = document.createElement("div");
    banner.className = "timeline-banner error";
    banner.textContent = "error · " + (data.message || "unknown");
    timeline.append(banner);
  }

  window.ProbeRender = { appendOrUpdateTurnCard, appendFinding, markComplete, showError };
})();
```

- [ ] **Step 2: Create `probe.js`**

Create `src/earn_money/dashboard/templates/static/probe.js` with the spec's exact content:

```js
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
```

- [ ] **Step 3: Verify file sizes**

```bash
wc -l src/earn_money/dashboard/templates/static/probe.js src/earn_money/dashboard/templates/static/probe-render.js
```

Expected: each ≤150 lines.

- [ ] **Step 4: Existing server tests still pass (no logic change reached)**

```bash
uv run pytest tests/dashboard/ -q
```

- [ ] **Step 5: Manual smoke (optional)**

```bash
uv run python -m earn_money.dashboard.server --root . &
SERVER_PID=$!
sleep 1
curl -s http://127.0.0.1:8080/static/probe.js | head -3
curl -s http://127.0.0.1:8080/static/probe-render.js | head -3
kill $SERVER_PID
```

Expected: both files served as `application/javascript`, first lines of each visible.

- [ ] **Step 6: Commit**

```bash
git add src/earn_money/dashboard/templates/static/probe.js src/earn_money/dashboard/templates/static/probe-render.js
git commit -m "feat(dashboard): probe.js SSE client + probe-render.js textContent renderers"
```
