# Task 3 — Single-page HTML

**File:** Create `src/earn_money/dashboard/templates/index.html`.

Single HTML file with embedded CSS + JS. No frameworks, no
build step. Polls `/api/status` every **10 s** (pipeline state
doesn't change faster than that). Renders programs as cards in a
CSS-grid; shows `across` metrics as tile row at top. Computes
`last_synced` age on the client side from the ISO timestamp — no
duplicated age field on the wire.

## Sections

1. **`<head>`** — `<title>`, `<meta>` viewport, embedded `<style>`.
2. **`<header>`** — site title, "Last updated: <timestamp>" pill.
3. **`<section id="across">`** — 4 metric tiles:
   `total_findings`, `total_queued`, `suppression_rate_pct`,
   `first_verified_with_operator_note` (✓/✗ — labelled "First
   verified candidate" in the UI; the generic predicate avoids
   coupling the dashboard to a specific engagement).
4. **`<section id="programs">`** — one `<article>` per program:
   - Header: `<platform>/<slug>` + policy badge + last_synced age
   - FROZEN warning row if `frozen=true` (red)
   - Finding-state badges (queued, resolved_info, verified, etc.)
   - Top-queue table (hash, severity, vuln_class, asset, first_seen)
   - Recent runs strip (last 24h: tool · status · signal_count)
5. **`<footer>`** — refresh interval indicator.
6. **`<script>`** at bottom — fetch loop + render functions.

## TDD note

This file is HTML/CSS/JS — no direct unit tests. The contract is
tested by `02-server.md`'s "/ returns HTML 200" test and the
integration test in `05-integration.md` (which loads `/` in a
real HTTP client and parses key strings out).

## Acceptance — load in a real browser

After the server is running:
```bash
ssh -L 8080:localhost:8080 recon-vps
xdg-open http://localhost:8080   # or open the URL in any browser
```

Verify visually: data appears within 10 s; refresh indicator ticks;
no console errors; CSS-grid responsive at ≥ 800 px width.

## Steps

- [ ] **1. Write the HTML page** following the sections above.
- [ ] **2. `make smoke`** green (no Python changes; just confirms
  nothing else broke).
- [ ] **3. Commit** as `feat(dashboard): single-page HTML with 10s polling and CSS-grid layout`.
- [ ] **4. `/simplify`** pass.
