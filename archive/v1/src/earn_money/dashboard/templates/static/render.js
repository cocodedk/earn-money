"use strict";

// XSS-safe DOM builders. Every API value goes through textContent /
// createTextNode — innerHTML is intentionally absent. Whitelists below
// gate the only fields we interpolate into class names.

const POLICY_VALUES = new Set(["rate-limited-OK", "manual-only", "ambiguous"]);
const SEVERITY_VALUES = new Set(["critical", "high", "medium", "low", "info", "unknown"]);
const STATUS_VALUES = new Set(["success", "partial", "failed", "skipped", "in_progress"]);

const acrossEl   = document.getElementById("across");
const programsEl = document.getElementById("programs");

function el(tag, attrs, text) {
  const e = document.createElement(tag);
  if (attrs) for (const k of Object.keys(attrs)) {
    if (k === "data") {
      for (const d of Object.keys(attrs.data)) e.dataset[d] = attrs.data[d];
    } else e.setAttribute(k, attrs[k]);
  }
  if (text !== undefined && text !== null) e.appendChild(document.createTextNode(String(text)));
  return e;
}
function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toISOString().replace("T", " ").replace(/:\d{2}\.\d+Z$/, "Z");
}
function ageLabel(iso) {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (isNaN(t)) return iso;
  const secs = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (secs < 60)    return secs + "s ago";
  if (secs < 3600)  return Math.round(secs / 60)   + "m ago";
  if (secs < 86400) return Math.round(secs / 3600) + "h ago";
  return Math.round(secs / 86400) + "d ago";
}
function safeClass(value, whitelist, fallback) {
  return whitelist.has(value) ? value : fallback;
}

function renderAcross(across) {
  acrossEl.replaceChildren();
  const tile = (label, value, opts = {}) => {
    const node = el("div", { class: "metric" });
    node.appendChild(el("span", { class: "label" }, label));
    const v = el("span", { class: "value" + (opts.class ? " " + opts.class : "") });
    v.appendChild(document.createTextNode(String(value)));
    if (opts.unit) v.appendChild(el("span", { class: "unit" }, opts.unit));
    node.appendChild(v);
    return node;
  };
  acrossEl.appendChild(tile("Total queued",   across.total_queued ?? 0));
  acrossEl.appendChild(tile("Total findings", across.total_findings ?? 0));
  acrossEl.appendChild(tile(
    "Suppression",
    Math.round((across.suppression_rate_pct ?? 0) * 10) / 10,
    { unit: "%" }
  ));
  const ok = !!across.first_verified_with_operator_note;
  acrossEl.appendChild(tile("First verified", ok ? "✓" : "✗",
                            { class: ok ? "good" : "bad" }));
}

// The aggregator owns the canonical FindingState set, which can grow
// without a JS-side release. Rather than ship a whitelist that drifts,
// strip anything outside the kebab/snake alphabet before interpolating
// into a class attribute — same defensive shape as CSS.escape.
function safeStateClass(name) {
  return name.replace(/[^a-z0-9_-]/gi, "");
}

function renderStates(states) {
  const row = el("div", { class: "states" });
  for (const [name, n] of Object.entries(states || {})) {
    if (!Number.isFinite(n) || n <= 0) continue;
    const s = el("span", { class: "state " + safeStateClass(name) });
    s.appendChild(el("span", { class: "name" }, name.replace(/_/g, " ")));
    s.appendChild(el("span", { class: "n" }, n));
    row.appendChild(s);
  }
  if (!row.childNodes.length) row.appendChild(el("span", { class: "empty" }, "no findings yet"));
  return row;
}

function renderQueueTable(top) {
  if (!top || !top.length) return el("div", { class: "empty" }, "no queued candidates");
  const t = el("table", { class: "qtbl" });
  const head = el("thead");
  const hr = el("tr");
  ["hash", "sev", "class", "asset", "first seen"].forEach(h => {
    const th = el("th", null, h);
    th.setAttribute("scope", "col");
    hr.appendChild(th);
  });
  head.appendChild(hr); t.appendChild(head);
  const body = el("tbody");
  for (const r of top) {
    const tr = el("tr");
    tr.appendChild(el("td", { class: "hash" }, (r.hash || "").slice(0, 8)));
    const sevTd = el("td");
    const sev = safeClass(r.severity, SEVERITY_VALUES, "unknown");
    sevTd.appendChild(el("span", { class: "sev " + sev }, sev));
    tr.appendChild(sevTd);
    tr.appendChild(el("td", { class: "vc" }, r.vuln_class || ""));
    tr.appendChild(el("td", { class: "asset" }, r.asset || ""));
    tr.appendChild(el("td", { class: "ts" }, ageLabel(r.first_seen)));
    body.appendChild(tr);
  }
  t.appendChild(body);
  return t;
}

function renderRunsStrip(runs) {
  if (!runs || !runs.length) return el("div", { class: "empty" }, "no recent runs");
  const strip = el("div", { class: "runs" });
  for (const r of runs) {
    const chip = el("span", { class: "run" });
    chip.appendChild(el("span", { class: "rtool" }, r.tool || "?"));
    const st = safeClass(r.status, STATUS_VALUES, "skipped");
    chip.appendChild(el("span", { class: "rstatus " + st }, st));
    chip.appendChild(el("span", null, "· " + (r.signal_count || 0) + " sigs"));
    strip.appendChild(chip);
  }
  return strip;
}

function renderPrograms(programs) {
  programsEl.replaceChildren();
  if (!programs.length) {
    programsEl.appendChild(el("div", { class: "empty" }, "no programs registered"));
    return;
  }
  let idx = 0;
  for (const p of programs) {
    idx += 1;
    const a = el("article", {
      class: "program", "aria-labelledby": "p" + idx + "-title",
      data: { index: String(idx).padStart(2, "0") },
    });
    a.style.setProperty("--i", String(idx - 1));

    const head = el("div", { class: "prog-head" });
    const title = el("span", { class: "prog-title", id: "p" + idx + "-title" });
    title.appendChild(el("span", { class: "platform" }, p.platform || "?"));
    title.appendChild(el("span", { class: "sep" }, "/"));
    title.appendChild(el("span", { class: "slug" }, p.slug || "?"));
    head.appendChild(title);
    const policy = safeClass(p.policy, POLICY_VALUES, "ambiguous");
    head.appendChild(el("span", { class: "policy " + policy }, p.policy || "unknown"));
    head.appendChild(el("span", { class: "prog-synced" }, "synced " + ageLabel(p.last_synced)));
    a.appendChild(head);

    if (p.frozen) {
      a.appendChild(el("div", { class: "frozen-row" }, "FROZEN: " + (p.frozen_reason || "no reason recorded")));
    }
    if (p.error) {
      a.appendChild(el("div", { class: "error-row" }, "ERROR: " + p.error));
    }
    a.appendChild(renderStates(p.finding_states || {}));
    a.appendChild(renderQueueTable(p.top_queue || []));
    a.appendChild(renderRunsStrip(p.recent_runs || []));
    programsEl.appendChild(a);
  }
}
