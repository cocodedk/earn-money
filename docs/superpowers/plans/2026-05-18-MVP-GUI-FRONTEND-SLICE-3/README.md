# MVP-GUI Frontend Slice 3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the deferred drill-down surfaces from `08-findings.md`, `09-evidence.md`, and `07-target-result.md`. After slice 3, the operator can land on `/findings` to browse + filter every finding peer's runners (1.1–1.7) have produced, click into a Finding for its full detail + linked evidence, do the same for `/evidence`, and open `/targets/:id/results` for a per-target rollup. Closes the last three "real page" gaps from the MVP-GUI spec; only Settings remains as a ComingSoon.

**Architecture:** Same stack and conventions as slices 1 and 2. New for slice 3:
- A small generic `<FiltersBar>` primitive that takes a list of filter definitions + current values + onChange and renders the dropdowns. Used by `FindingsList` (7 filters) and `EvidenceList` (5 filters). Avoids duplicating the filter UI per page.
- Backend filters are consumed via TanStack Query keys that include the active filter object, so changing a filter triggers a fresh fetch.
- Target result page fetches three resources scoped to the target via existing global endpoints with `?target=<id>` filter parameters — no new endpoints required (peer confirmed in a prior thread that the standard query filters are in place).

**Branch:** `feat/em-frontend-slice-3` in worktree `/home/cocodedk/0-projects/earn-money-frontend-slice-3/`. Cut from `feat/em-frontend-slice-2` tip `7da2494` (which itself sits on `origin/refactor/archive-v1` `e72fb30`). Rebase forward when peer's Phase 2 work lands.

**Conventional commits + post-commit /simplify** still apply per CLAUDE.md. Every task TDD-first.

## Out of scope for slice 3 (defer to slice 4+)

- SSE reconnect hardening (basic open → consume → close still ships)
- Operator triage UX (click-to-cycle `PATCH /api/findings/<id>/status/`)
- Settings page
- Markdown rendering for StubDetail body
- Seed-data button

## Phase index

| Phase | File | Tasks | Ships |
|-------|------|-------|-------|
| 0 | [phase-0-api-clients.md](phase-0-api-clients.md) | A–B | Findings + Evidence API hooks with filter querystrings |
| 1 | [phase-1-findings.md](phase-1-findings.md) | C–E | `<FiltersBar>` primitive; FindingsList page; FindingDetail page |
| 2 | [phase-2-evidence.md](phase-2-evidence.md) | F–G | EvidenceList + EvidenceDetail page |
| 3 | [phase-3-target-result.md](phase-3-target-result.md) | H–I | Target result page composing scan-runs + findings + evidence + events for one target |
| 4 | [phase-4-integration.md](phase-4-integration.md) | J–K | Route swaps in App; slice-3 e2e test |
| 5 | [phase-5-final-pass.md](phase-5-final-pass.md) | — | Full coverage, vite build, compose smoke vs live backend |

## Acceptance for slice 3

When the entire plan is green:

- `npm run test:coverage` → 100/100/100/100 on `src/**/*.{ts,tsx}` minus the documented exclusions.
- Four sidebar items previously routing to `<ComingSoon/>` now route to real pages: Findings list + detail, Evidence list + detail. (Only Settings stays as ComingSoon.)
- `/targets/:id/results` renders the per-target rollup.
- Compose smoke (live backend): operator can run stub 1.1 against the three lab fixtures, then browse `/findings?stub=1.1` to filter and `/findings/:id` to drill into individual results with linked evidence rows.
