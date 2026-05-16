# Task 9 — `index.html` tabs + `tabs.js`

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/08-frontend-html-tabs.md`

**Files:**
- Modify: `src/earn_money/dashboard/templates/index.html`
- Create: `src/earn_money/dashboard/templates/static/tabs.js`

This is a pure DOM addition — tab bar, RECON sections wrapped in `<div id="tab-recon">`, new PROBE section, CSS link in `<head>`, three new `<script>` tags at end of body. No unit tests (vanilla DOM, no logic worth mocking) — manual smoke only.

- [ ] **Step 1: Add the CSS link in `<head>`**

In `src/earn_money/dashboard/templates/index.html`, immediately after the existing `<link rel="stylesheet" href="/static/panels.css">` line, add:

```html
<link rel="stylesheet" href="/static/probe.css">
```

Place this with the other stylesheets so the timeline doesn't paint unstyled while the rest of the body parses.

- [ ] **Step 2: Insert the tab bar above the first `<h2 class="rule">`**

Before the line `<h2 class="rule"><span>§ 01 — SUMMARY</span></h2>` (line 24 in the existing file), insert:

```html
<nav class="tabs" role="tablist">
  <button class="tab active" data-tab="recon" role="tab" aria-selected="true">RECON</button>
  <button class="tab"        data-tab="probe" role="tab" aria-selected="false">PROBE</button>
</nav>

<div id="tab-recon" role="tabpanel">
```

- [ ] **Step 3: Close the RECON tab wrapper and add the PROBE panel**

After the existing `<section id="programs">…</section>` block (the §04 PROGRAMS section, around line 34), close the recon `<div>` and add the probe panel:

```html
</div>

<div id="tab-probe" role="tabpanel" hidden>
  <h2 class="rule"><span>§ 01 — PROBE LAUNCHER</span></h2>
  <section id="probe-launcher">
    <form id="probe-form" autocomplete="off">
      <label>Base URL <input name="base_url" type="url" required></label>
      <label>RoE profile <input name="roe_profile" type="text" placeholder="roe/local-lab.yaml"></label>
      <label>Max turns <input name="max_turns" type="number" min="1" max="50" value="10"></label>
      <label>Platform <input name="platform" type="text" placeholder="local"></label>
      <label>Program
        <input name="program" type="text" placeholder="(optional — leave empty for local/ad-hoc lab targets)">
        <small class="hint">Required when probing live registered programs so the FROZEN gate fires; leave empty only for local/ad-hoc lab targets.</small>
      </label>
      <button type="submit" id="probe-run">RUN</button>
    </form>
  </section>

  <h2 class="rule"><span>§ 02 — LIVE TIMELINE</span></h2>
  <section id="probe-timeline" aria-live="polite"></section>
</div>
```

The `</main>` close tag stays where it was.

- [ ] **Step 4: Add the three new `<script>` tags at end of `<body>`**

After the existing `<script src="/static/dashboard.js"></script>` line, append:

```html
<script src="/static/tabs.js"></script>
<script src="/static/probe-render.js"></script>
<script src="/static/probe.js"></script>
```

Order matters: `tabs.js` first (so tab switching works even before the probe scripts load); `probe-render.js` before `probe.js` (the latter calls into the former's `window.ProbeRender`).

- [ ] **Step 5: Create `tabs.js`**

Create `src/earn_money/dashboard/templates/static/tabs.js`:

```js
(function () {
  const tabs = document.querySelectorAll(".tabs .tab");
  const panels = document.querySelectorAll("[id^='tab-']");

  function show(name) {
    panels.forEach(p => p.hidden = (p.id !== "tab-" + name));
    tabs.forEach(t => {
      const on = t.dataset.tab === name;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  function chosenFromHash() {
    const m = /^#tab=(\w+)$/.exec(location.hash || "");
    return m ? m[1] : "recon";
  }

  tabs.forEach(t => t.addEventListener("click", () => {
    const name = t.dataset.tab;
    location.hash = "tab=" + name;
    show(name);
  }));

  window.addEventListener("hashchange", () => show(chosenFromHash()));
  show(chosenFromHash());
})();
```

- [ ] **Step 6: Verify file sizes**

```bash
wc -l src/earn_money/dashboard/templates/index.html src/earn_money/dashboard/templates/static/tabs.js
```

Expected: `index.html` under 200; `tabs.js` under 150.

- [ ] **Step 7: Existing server tests still pass (the new tab structure shouldn't break them)**

```bash
uv run pytest tests/dashboard/ -q
```

- [ ] **Step 8: Manual smoke (optional, requires running server)**

```bash
uv run python -m earn_money.dashboard.server --root . &
SERVER_PID=$!
sleep 1
curl -s http://127.0.0.1:8080/ | grep -E 'tab-(recon|probe)|tabs.js'
kill $SERVER_PID
```

Expected: the tab markup and `tabs.js` `<script>` tag appear in the rendered HTML.

- [ ] **Step 9: Commit**

```bash
git add src/earn_money/dashboard/templates/index.html src/earn_money/dashboard/templates/static/tabs.js
git commit -m "feat(dashboard): tab bar in index.html + tabs.js switcher"
```
