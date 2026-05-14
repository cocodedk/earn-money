"use strict";

// Across-program panels: ACTIVE SCANS + RECENT SIGNALS.
// Depends on render.js for el(), safeClass(), SEVERITY_VALUES, ageLabel.

const activeRunsEl = document.getElementById("active-runs");
const recentSignalsEl = document.getElementById("recent-signals");

const SIGNAL_TYPE_VALUES = new Set([
  "template_match",
  "takeover_vulnerable",
  "leaked_secret",
  "exposed_sourcemap",
  "introspection_enabled",
]);

function renderActiveRuns(runs) {
  activeRunsEl.replaceChildren();
  if (!runs || !runs.length) {
    activeRunsEl.appendChild(el("div", { class: "empty" }, "no scans in flight"));
    return;
  }
  const strip = el("div", { class: "runs" });
  for (const r of runs) {
    const chip = el("span", { class: "run active" });
    chip.appendChild(el("span", { class: "rtool" }, r.tool || "?"));
    chip.appendChild(el("span", { class: "rstatus in_progress" }, "in flight"));
    chip.appendChild(el("span", null, "· " + (r.platform || "?") + "/" + (r.slug || "?")));
    chip.appendChild(el("span", { class: "rage" }, ageLabel(r.started_at)));
    strip.appendChild(chip);
  }
  activeRunsEl.appendChild(strip);
}

function renderRecentSignals(signals) {
  recentSignalsEl.replaceChildren();
  if (!signals || !signals.length) {
    recentSignalsEl.appendChild(el("div", { class: "empty" }, "no signals yet"));
    return;
  }
  const t = el("table", { class: "qtbl signals" });
  const head = el("thead");
  const hr = el("tr");
  ["when", "tool", "type", "asset", "program"].forEach(h => {
    const th = el("th", null, h);
    th.setAttribute("scope", "col");
    hr.appendChild(th);
  });
  head.appendChild(hr); t.appendChild(head);
  const body = el("tbody");
  for (const r of signals) {
    const tr = el("tr");
    tr.appendChild(el("td", { class: "ts" }, ageLabel(r.observed_at)));
    tr.appendChild(el("td", { class: "vc" }, r.tool || "?"));
    const st = safeClass(r.signal_type, SIGNAL_TYPE_VALUES, "template_match");
    const typeTd = el("td");
    typeTd.appendChild(el("span", { class: "sigtype " + st },
                          (r.signal_type || "").replace(/_/g, " ")));
    tr.appendChild(typeTd);
    tr.appendChild(el("td", { class: "asset" }, r.asset || ""));
    tr.appendChild(el("td", { class: "vc" },
                      (r.platform || "?") + "/" + (r.slug || "?")));
    body.appendChild(tr);
  }
  t.appendChild(body);
  recentSignalsEl.appendChild(t);
}
