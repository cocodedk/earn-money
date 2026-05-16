# 09 — Frontend · probe client (form, SSE, renderers)

Two files: `probe.js` (form + SSE driver) and `probe-render.js` (DOM renderers). Both vanilla, both ≤150 lines, both `textContent`-only.

## `probe.js` — form + EventSource client

Owns:
- Form submit → `fetch("/api/probe/start", {method:"POST", body:JSON.stringify(...)})`.
- Opens `EventSource("/api/probe/stream?run_id=<id>")` on a 200 response, threading the `run_id` from the POST so the server can reject mismatched streams (see [06-server-routes.md](06-server-routes.md)).
- Dispatches each event by name to renderers in `probe-render.js`.
- **`state.closed` guard** (resolves cursor-agent review #6): the first `done` or `probe_error` event sets `closed=true` and calls `es.close()`. All subsequent handlers no-op. This neutralises EventSource's auto-reconnect.
- Disables the RUN button while a probe is running; re-enables on `done` / `probe_error` / transport-level disconnect (`es.onerror`).

```js
(function () {
  const form = document.getElementById("probe-form");
  const runBtn = document.getElementById("probe-run");
  const timeline = document.getElementById("probe-timeline");
  const state = { es: null, closed: false, run_id: null };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.es) return;                    // belt: button is also disabled
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
      // Network failure (server down, DNS, etc.) — re-enable the button
      // and surface the error. Without this catch, RUN stays disabled
      // forever after a network blip.
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
    // Pass run_id so the server can reject mismatches (e.g. stale tabs).
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
    // Application-level errors emitted by ProbeRunner (renamed from `error`
    // to avoid collision with EventSource's built-in transport-error event).
    es.addEventListener("probe_error", (e) => {
      if (state.closed) return;
      state.closed = true;
      const payload = JSON.parse(e.data);
      ProbeRender.showError(timeline, payload);
      es.close();
      state.es = null;
      runBtn.disabled = false;
    });
    // Transport-level disconnect (network blip, server close). Distinct from
    // probe_error above — no payload, fires only on connection trouble.
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

EventSource's built-in `onerror` fires on connection loss with no `data` — that's the transport channel and the client wires it to `es.onerror` separately from the application-level `probe_error` event. We treat any post-`done`/`probe_error` `onerror` as a no-op (the `state.closed` guard), and the first one as the disconnect we render. `retry: 0` (sent by the server, see [06-server-routes.md](06-server-routes.md)) plus the `closed` guard together kill any auto-reconnect.

## `probe-render.js` — DOM renderers (no `innerHTML`)

Target: ≤120 lines. Single chokepoint for all DOM mutation. Every value uses `textContent`. The file exposes `window.ProbeRender = { appendOrUpdateTurnCard, appendFinding, markComplete, showError }`.

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
      // Pre-parse update: model id + token estimate + raw LLM reply.
      header.querySelector(".model-id").textContent = data.model || "?";
      header.querySelector(".tokens").textContent = "~" + (data.estimated_tokens || 0) + "t";
      card.querySelector(".slot-action").textContent = data.raw_excerpt || "";
    } else if (data.stage === "action_parsed") {
      // Post-parse update: replace raw with the structured action, and
      // flag recoveries here (the parse_recovered field lives on this
      // stage, not on action_pending — parsing hasn't happened yet there).
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

No `innerHTML` anywhere — every assignment is `.textContent`, every node is `document.createElement` + `.append`. Safe even if the model echoes script tags into the body excerpt.

**Namespace note**: The global is `window.ProbeRender`, not the generic `window.Render`, so we don't collide with any future renderer module the dashboard might add. The existing `render.js` / `render_panels.js` / `dashboard.js` declare their state in module scope (no `window.` assignments) — verified at spec-write time — so there's no collision today either.

## Event ordering — what the renderer assumes

The renderer trusts the SSE contract in [07-sse-contract.md](07-sse-contract.md):

- A `turn` card is created on the first `turn` event for that `turn` number, regardless of `stage`. If `policy` arrives before `action_pending` (it won't, but defensive), the card still exists; the action slot is just empty.
- A `finding` event without a prior `turn` event for that `turn` number creates the card (via `$card`) so a finding never lands in a void.
- `markComplete` and `showError` produce *banners*, not turn cards. They terminate the timeline visually.

## Test impact

- `probe.js`: no Jest/Vitest setup in this project. Behaviour is verified via the server-side `tests/dashboard/test_probe_routes.py` SSE frame assertions plus the manual smoke in [12-tests.md](12-tests.md).
- `probe-render.js`: same — manual smoke. If we ever add JS unit tests, this is a good first target because the functions are pure (DOM in → DOM out).

## What's NOT here

- Charting / token-usage graphs over time. Single integer per card is enough for v1.
- Filtering / search over the timeline. `Cmd-F` on the page works.
- WebSocket fallback. SSE is the wire protocol.
- Animation library. CSS-only transitions if any animation is wanted, otherwise none.
