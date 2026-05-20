# Scope-enforcement layer for v2 backend

> Branch root: `feat/em-backend-scope-enforcement` (stacked on `feat/em-backend-well-known-paths`). The plan-tree itself is committed on this same branch; no separate `-plan` branch — the plan + every implementation slice share one stack tip.
> Goal owner: operator-set 2026-05-21 — "we must run phase 1 against a hackerone target"
> Implements: the safety scaffolding that lets v2's Phase 1 stubs fire against real bug-bounty programs without violating CLAUDE.md's hard rules ("scope is gospel", "three-tier policy", "two human gates", "kill-switch", "per-program RoE").

## Summary

v2 backend currently has **zero** references to `programs/`, `scope.md`, `roe.md`, or `RECON_ENABLED`. Dispatching a Phase 1 stub against `www.algolia.com` today would probe the host unconditionally — no scope check, no out-of-scope rejection, no master kill-switch. Before any real HackerOne / Bugcrowd / Intigriti scan can safely fire, v2 needs the scope-enforcement layer that v1 (parked at `archive/v1/src/earn_money/{scope,flags,config}.py`) shipped.

This stack rebuilds that layer cleanly for v2's Django + Celery + per-stub-runner architecture. Programs/credentials/algolia-scope are already in place; the gap is purely runtime enforcement.

## Execution order

Run slices strictly in table order: AUDIT, A, B, C, D, E, F, G, H. Slice D depends on B+C exceptions and settings wiring; slice E depends on C+D's resolved `Program` runtime context; slice F must land before G so every remaining fetcher inherits the same rate-limit call site. Do not start live smoke until H verifies the runner inventory from G.

## Preconditions to verify in AUDIT

* The implementation branch is stacked on `feat/em-backend-well-known-paths`, and the v2 backend paths in [`file-structure.md`](file-structure.md) still exist.
* `programs/hackerone/algolia/{scope.md,roe.md}` exists at the repo/programs root and matches the audited v1 frontmatter format.
* There is a shared cache or Redis primitive suitable for cross-worker rate limiting. If not, slice F must cap worker concurrency to one for any live scan and record the distributed limiter follow-up before H.

## Tree contents

| File | Purpose |
|------|---------|
| [`decisions/locked-in-architecture.md`](decisions/locked-in-architecture.md) | Seven architecture calls locked in before code |
| [`file-structure.md`](file-structure.md) | Exact file paths to create (`apps/programs/` + integration points) |
| [`tasks/00-slice-AUDIT.md`](tasks/00-slice-AUDIT.md) | Pre-implementation audit (v1 archive + CLAUDE.md hard rules) |
| [`tasks/01-slice-A-scope-matcher.md`](tasks/01-slice-A-scope-matcher.md) | Scope dataclass + wildcard hostname matcher |
| [`tasks/02-slice-B-flags.md`](tasks/02-slice-B-flags.md) | RECON_ENABLED kill-switch + per-program freeze |
| [`tasks/03-slice-C-loader.md`](tasks/03-slice-C-loader.md) | Program loader + RoE dataclass + mtime cache |
| [`tasks/04-slice-D-preflight.md`](tasks/04-slice-D-preflight.md) | Scan-run pre-flight scope check |
| [`tasks/05-slice-E-fetcher-scope.md`](tasks/05-slice-E-fetcher-scope.md) | Fetcher-level scope check + OUT_OF_SCOPE_REJECTED event |
| [`tasks/06-slice-F-rate-limit.md`](tasks/06-slice-F-rate-limit.md) | Per-program token-bucket rate limit |
| [`tasks/07-slice-G-wire-stubs.md`](tasks/07-slice-G-wire-stubs.md) | Wire all Phase 1 stubs through scope enforcement |
| [`tasks/08-slice-H-audit-smoke.md`](tasks/08-slice-H-audit-smoke.md) | Post-impl audit + live algolia smoke |
| [`persistence-wiring.md`](persistence-wiring.md) | Event wiring + non-DB runtime objects |
| [`verification.md`](verification.md) | Completion gates |
| [`merge-gate.md`](merge-gate.md) | Merge-heuristic checkpoint |
| [`rollback.md`](rollback.md) | Per-slice + whole-stack revert procedures |
| [`out-of-scope.md`](out-of-scope.md) | Deferred follow-ups (tracked) |
