# Phase 1 closeout — stubs 1.19 + well_known_paths (absorbs 1.20–1.25)

> Branch root: `feat/em-backend-phase-1-closeout-plan` (stacked on `feat/em-backend-1.18-closure`)
> Goal owner: operator-set 2026-05-20 — "finishing 01-information-gathering is the goal right now"
> Implements: cookbook specs 1.19 (sql-orm-errors) + 1.20–1.25 absorbed into a single `well_known_paths` stub with 6 families
> Closes Phase 1: stubs 1.1–1.17 already shipped (PR #29 squash `c4087d9`); 1.18 closure committed `52904ac`

## Summary

**Status going in (verified 2026-05-20):**
- Frontmatter `status: done` (5/278): 1.10, 1.11, 1.12, 1.13, 1.18.
- Code-shipped BUT frontmatter still `pending` (13 specs): 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.14, 1.15, 1.16, 1.17. Pre-existing reconciliation gap tracked in [`out-of-scope.md`](out-of-scope.md); not part of this closeout.
- Not shipped (7 specs): 1.19, 1.20, 1.21, 1.22, 1.23, 1.24, 1.25 — THIS stack ships them.

Two new backend stubs land the remaining 1.19–1.25 coverage:

1. **`sql_orm_errors`** — body-signature classifier on HTTP response bodies. Mirrors the architecture of `stack_traces` (1.16) and `verbose_api_errors` (1.17): signatures → matcher → classifier → runner → persistence. Standalone stub. **Pre-implementation spec audit FIRST** (slice 00-AUDIT), then build.
2. **`well_known_paths`** — well-known-path probe with 6 families: `env`, `git`, `config_files`, `logs`, `backup_archives`, `db_dumps`. Absorbs specs 1.20–1.25 via **single** `@register("1.20")` (mirrors `debug_pages` `@register("1.10")` precedent, which absorbs 1.18 without a second registration). Shared safety controls (soft-404 detection, HEAD-first probing, Range-bounded GETs, byte caps, content-type guards, binary magic, secret redaction, same-origin redirects, rate limits) live in one place. Findings retain family-specific category + signatures so `.git` exposure, env leak, log leak, archive exposure, and db-dump exposure remain distinct in findings and reporting. **Pre-implementation 6-spec consolidated audit FIRST** (slice 04b-AUDIT), then build.

Specs 1.21–1.25 each get the same closure treatment as 1.18 + 1.20: `status: done` + closure note pointing to `well_known_paths`.

## Tree contents

| File | Purpose |
|------|---------|
| [`decisions/locked-in-architecture.md`](decisions/locked-in-architecture.md) | Four architecture calls locked in before code |
| [`file-structure.md`](file-structure.md) | Exact file paths to create per stub (including apps.py wiring + HEAD-first fetcher policy) |
| [`tasks/00-slice-19-AUDIT-spec-review-first.md`](tasks/00-slice-19-AUDIT-spec-review-first.md) | sql_orm_errors PRE-implementation spec audit |
| [`tasks/01-slice-19-A-signatures.md`](tasks/01-slice-19-A-signatures.md) | sql_orm_errors signatures + matcher |
| [`tasks/02-slice-19-B-classifier.md`](tasks/02-slice-19-B-classifier.md) | sql_orm_errors classifier + Verdict + apps.py wiring |
| [`tasks/03-slice-19-C-runner.md`](tasks/03-slice-19-C-runner.md) | sql_orm_errors runner + redaction + persistence |
| [`tasks/04-slice-19-D-spec-review.md`](tasks/04-slice-19-D-spec-review.md) | sql_orm_errors POST-implementation audit + status flip |
| [`tasks/04b-slice-WKP-AUDIT-spec-review-first.md`](tasks/04b-slice-WKP-AUDIT-spec-review-first.md) | well_known_paths PRE-implementation 6-spec consolidated audit |
| [`tasks/05-slice-WKP-A-families-signatures-soft404.md`](tasks/05-slice-WKP-A-families-signatures-soft404.md) | well_known_paths families + signatures + soft-404 + apps.py wiring |
| [`tasks/06-slice-WKP-B-fetcher-classifier.md`](tasks/06-slice-WKP-B-fetcher-classifier.md) | well_known_paths HEAD-first + Range fetcher + per-family classifier |
| [`tasks/07-slice-WKP-C-runner-persistence.md`](tasks/07-slice-WKP-C-runner-persistence.md) | well_known_paths runner + redaction + per-family persistence |
| [`tasks/08-slice-WKP-D-closures-spec-review.md`](tasks/08-slice-WKP-D-closures-spec-review.md) | 1.21–1.25 frontmatter closures (1.20 already mapped via @register) + post-implementation audit |
| [`persistence-wiring.md`](persistence-wiring.md) | Evidence/Finding shape wiring + status/severity/dedup vocabulary |
| [`verification.md`](verification.md) | Final test gates (Phase 1 close criteria) |
| [`merge-gate.md`](merge-gate.md) | Merge-heuristic checkpoint + rollback pointer |
| [`rollback.md`](rollback.md) | Per-slice + whole-stack revert procedures |
| [`out-of-scope.md`](out-of-scope.md) | Deferred follow-ups (tracked) |

Stack ordering: `feat/em-backend-1.19-sql-orm-errors` → `feat/em-backend-well-known-paths` (one branch per stub per [[project-stacked-branch-convention]]).
