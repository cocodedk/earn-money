# 2026-05-12 — Five-Step Cut: shrink the remaining roadmap

**Status:** Active. Both independent reviewers (Claude opus-4.7 + cursor gpt-5.5-extra-high) agreed 100% on the cuts below.

## What changed

A first-principles pass on the remaining-phase roadmap (Phases 3c, 3d, 4, 5, 6) — using Elon Musk's five-step algorithm (Question → Delete → Simplify → Speed → Automate) — concluded that most pre-emptive automation should be cut in favour of shipping the smallest earning loop first. Phase 3a + 3b already produce real signals and queue candidates; we have not yet proven that one of those candidates can travel through verification → submission → payment. Building more signal sources before proving that path is the canonical "polished work on the wrong question" mistake.

## Decisions

### 🟢 Next (build now)

- `bin/submit` — bash helper wrapping `triage.history.transition_state` to move a finding `_verified → _submitted` with audit history. Mostly shell. Non-negotiable because the second human gate must be in code.
- `bin/ack-freeze` — ~10 lines shell. Prompt for reason → append to `programs/<platform>/<slug>/freeze-acks.log` → `rm FROZEN`. No Python module, no `ops_runs` table, no transactional ceremony.
- `templates/report-draft.md` — committed report template with frontmatter placeholders.
- `bin/draft` — small (~20 lines) Python helper that fills the template from a finding row.

Goal: submit one real candidate to HackerOne and observe the outcome.

### 🟡 Measure (operate, not build)

Phase 5 stays in the roadmap but as **measurement, not build**. No new code. Operator runs the loop on one program. Track time spent, submissions, dupes, N/As, paid amounts. **Month-3 kill/pivot gate**: trending toward >€500/mo with clean human-edited reports? → continue. Not? → kill or pivot.

### 🅿️ Parked (unpark only on specific signals)

| Parked item | Unpark when… |
|---|---|
| `bin/status` (on-demand digest command) | Manual queue inspection becomes annoying. |
| ffuf as a documented manual procedure | First time content discovery is actually needed for a target. |
| ffuf as a scheduled runner | Manual ffuf has surfaced ≥2 real findings worth automating. |
| katana crawler runner | A target with heavy SPA/client-side routing requires it. |
| 08:00 cron-generated daily digest | Multiple programs active OR `bin/status` on-demand becomes painful. |
| Phone ping via `claude-email`/`claude-chat` bus | Away-from-desk operation becomes common (travel, alerting on a high-priority finding). |
| systemd timer chain on the VPS | Unattended operation actually needed (≥2 programs OR daily cadence pays rent). |
| `ops_runs` table + audit machinery for non-recon ops | When a non-recon ops action other than freeze-ack needs durable audit. |
| Multi-program scaling | One program is proven and earning. |

### ❌ Dropped (out of active scope)

- **Phase 6 — FITS Express mini-audit product**. Conditional on Phase 5 hitting €500/mo. Returns as its own project if Phase 5 proves the underlying skill — not as the next thing built. Removed from the active phasing list.

## Affected files (state on this commit)

- `docs/superpowers/plans/2026-05-12-phase-3c-katana-ffuf.md` — top banner marks the plan **PARKED**. Implementation tasks remain as a future reference; only revisit when an unpark signal fires.
- `docs/superpowers/specs/2026-05-12-phase-3-design.md` — Phase 3d section gets a top note that most of 3d is parked; only `bin/ack-freeze` (shell) survives in 3d.
- `docs/superpowers/specs/2026-05-12-earn-money-design.md` — Phasing section gets a note pointing here and reframes Phase 5/6.
- `README.md` — Status table reflects the new tags (✅ DONE / 🟢 NEXT / 🟡 MEASURE / 🅿️ PARKED / ❌ DROPPED).

## What might force pieces back in

This decision record stays honest by being explicit about its own falsifiers:

- Queue volume — if `findings/_queue/` grows past what manual review can absorb in the daily 30–60 min slot, build `bin/status` first, then the cron digest.
- Repeated submissions — if writing 3+ reports surfaces obvious boilerplate, the Python report drafter earns its keep.
- Freeze frequency — if FROZEN flags fire often, the lightweight `bin/ack-freeze` shell helper might want a real audit trail in `ops_runs`.
- Manual exploration value — if Babak repeatedly finds value in JS-discovered URLs (katana) or content-discovered paths (ffuf), schedule them in that order.
- Real earnings without scaling — if one program reliably earns and the operator's bottleneck shifts to "I want more programs," unpark multi-program scaling.

## Why this is a good record to revisit

The decisions above are not permanent. They reflect *today's* bottleneck: prove the earning loop. When the bottleneck shifts, this record is the place to look up "what did past-us decide to defer, and on what signal should we resurrect it?"
