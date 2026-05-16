# 08 — Frontend · HTML + tab switching

Two files touched here: `index.html` (modified) and `tabs.js` (new). Together they introduce the tab-bar UI without changing any RECON-tab behaviour.

## `index.html` — tab bar + wrapped sections

Insert above the first `<h2 class="rule">` (today at line 24 of `templates/index.html`):

```html
<nav class="tabs" role="tablist">
  <button class="tab active" data-tab="recon" role="tab" aria-selected="true">RECON</button>
  <button class="tab"        data-tab="probe" role="tab" aria-selected="false">PROBE</button>
</nav>

<div id="tab-recon" role="tabpanel">
  <!-- existing 4 sections move here UNCHANGED:
       §01 SUMMARY, §02 ACTIVE SCANS, §03 RECENT SIGNALS, §04 PROGRAMS -->
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

One new `<link>` in `<head>` (alongside `tokens.css`, `dashboard.css`, `panels.css`):

```html
<link rel="stylesheet" href="/static/probe.css">
```

Three new `<script>` at the end of `<body>` (after the existing `render.js` / `render_panels.js` / `dashboard.js`):

```html
<script src="/static/tabs.js"></script>
<script src="/static/probe-render.js"></script>
<script src="/static/probe.js"></script>
```

CSS link sits with the other stylesheets in `<head>` so the browser doesn't paint the timeline unstyled while parsing the body. The new scripts load *after* the existing dashboard scripts so they can't collide with any global names those define.

## `tabs.js` — pure client-side switching

Target: ≤60 lines. No build step, no module loader. Vanilla DOM — matches the existing dashboard scripts.

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

Tab state in `location.hash` — refresh restores the tab without a localStorage write. No server round-trips.

## Accessibility

- Tab buttons carry `role="tab"` + `aria-selected`; panels carry `role="tabpanel"`.
- The `hidden` attribute (not just `display:none`) so screen readers skip the off-tab content.
- Tab order is keyboard-natural: tab buttons are real `<button>`s, so Enter/Space activate them.

## Not in this file

- The form's submit handler — that's in `probe.js` ([09-frontend-probe-client.md](09-frontend-probe-client.md)).
- The timeline renderers — that's in `probe-render.js` ([09-frontend-probe-client.md](09-frontend-probe-client.md)).
- The visual styling — that's in `probe.css` ([10-frontend-css.md](10-frontend-css.md)).

## Test impact

- No unit test for `tabs.js` (vanilla DOM, no logic worth mocking).
- Manual smoke: load the dashboard, click PROBE → form appears, RECON sections hide. Click RECON → form hides, RECON returns. Refresh on PROBE → PROBE still selected.
