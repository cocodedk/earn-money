"use strict";

// Polls /api/status every REFRESH_MS, hands the payload to render.js,
// and toggles the refresh-state indicator. Loaded after render.js so
// renderAcross / renderPrograms are defined when tick() first runs.

const REFRESH_MS = 30000;
const FETCH_TIMEOUT_MS = 8000;

const refreshEl  = document.getElementById("refresh");
const rlabelEl   = refreshEl.querySelector(".rlabel");
const updatedEl  = document.getElementById("updated");

let inflight = false;
// Memoize last meaningful payload so we skip a full DOM rebuild on the
// common quiet-recon case where /api/status reports no change. The
// aggregator stamps `generated_at` per request, so we exclude it from
// the signature — otherwise no two payloads would ever match.
let lastSig = "";

function setRefresh(state, label) {
  refreshEl.className = "live " + state;
  rlabelEl.textContent = label;
}

async function tick() {
  if (inflight) return;
  inflight = true;
  // No per-tick busy flash — the pulsing LIVE dot already signals
  // "alive". Page load starts in the HTML default `busy/CONNECTING`
  // state and flips to LIVE on the first success.
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), FETCH_TIMEOUT_MS);
  try {
    const r = await fetch("/api/status", { cache: "no-store", signal: ac.signal });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const sig = JSON.stringify({ across: data.across, programs: data.programs });
    if (sig !== lastSig) {
      renderAcross(data.across || {});
      renderPrograms(data.programs || []);
      lastSig = sig;
    }
    const stamp = data.generated_at ? fmtTime(data.generated_at) : "—";
    updatedEl.textContent = "last sync " + stamp;
    setRefresh("live", "LIVE");
    if (document.body.classList.contains("boot")) {
      // Boot animation runs once on the very first successful render.
      requestAnimationFrame(() => document.body.classList.remove("boot"));
    }
  } catch (e) {
    console.warn("dashboard: status fetch failed", e);
    setRefresh("stale", "STALE");
  } finally {
    clearTimeout(timer);
    inflight = false;
  }
}

document.body.classList.add("boot");
tick();
setInterval(tick, REFRESH_MS);
