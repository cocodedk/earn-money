# Phase 1 closeout — stubs 1.19 + well_known_paths (absorbs 1.20–1.25)

> Branch root: `feat/em-backend-phase-1-closeout-plan` (stacked on `feat/em-backend-1.18-closure`)
> Goal owner: operator-set 2026-05-20 — "finishing 01-information-gathering is the goal right now"
> Implements: cookbook specs 1.19 (sql-orm-errors) + 1.20–1.25 absorbed into a single `well_known_paths` stub with 6 families
> Closes Phase 1: stubs 1.1–1.17 already shipped (PR #29 squash `c4087d9`); 1.18 closure committed `52904ac`

## Summary

Two new backend stubs land Phase 1 to 100% spec coverage:

1. **`sql_orm_errors`** — body-signature classifier on HTTP response bodies. Mirrors the architecture of `stack_traces` (1.16) and `verbose_api_errors` (1.17): signatures → matcher → classifier → runner → persistence. Standalone stub.
2. **`well_known_paths`** — well-known-path probe with 6 families: `env`, `git`, `config_files`, `logs`, `backup_archives`, `db_dumps`. Absorbs specs 1.20–1.25 per the 1.10→1.18 precedent (codex-blessed direction call, 2026-05-20). Shared safety controls (soft-404 detection, byte caps, content-type guards, binary magic, secret redaction, rate limits) live in one place. Findings retain family-specific category + signatures so `.git` exposure, env leak, log leak, archive exposure, and db-dump exposure remain distinct in findings and reporting.

Specs 1.20–1.25 each get the same closure treatment as 1.18: `status: done` + closure note pointing to `well_known_paths`.

## Architecture decisions (locked in)

* **One stub for 1.20–1.25, not six.** Codex consult verdict 2026-05-20: identical core loop, shared safety controls matter, precedent established by 1.10→1.18. Don't flatten the finding taxonomy — preserve per-family `Finding.category` and `Finding.data.family`.
* **Stub 1.19 stays standalone.** It's a body-signature classifier, not a path probe — different shape from `well_known_paths`. Sharing would couple unrelated concerns.
* **No new shared types.** Evidence + Finding shapes are unchanged from PR #29. Per-family additions land under `Finding.data` keys, which is additive and frontend-tolerant per [[project-merge-coordination]] rule (2).
* **Soft-404 detection in `well_known_paths`** is a NEW shared control (not in `_shared` yet). Per-target SPA/soft-404 baseline cached per scan. If a candidate response shape matches the baseline → reject the candidate as a soft-404 false positive.

## File structure to create

### Stub 1.19 (`apps/stubs/sql_orm_errors/`)

* `__init__.py` — fires `@register("1.19")` on import
* `signatures.py` — Signature NamedTuple + per-DB/ORM regex set (PostgreSQL, MySQL, MSSQL, Oracle, SQLite, Django ORM, SQLAlchemy, Hibernate, ActiveRecord, Sequel, MongoDB error shapes)
* `signals.py` — matcher (regex search + named-group extraction)
* `classify.py` — Verdict NamedTuple → confidence ladder (`strong signal → high`, `framework_hint + error_status → medium`, `weak signal alone → low → reject`)
* `runner.py` — `run(target)` iterates candidate URLs (crawler import), fetches, classifies, persists
* `fetcher.py` — bounded GET with shared HTTP client; redirect policy + byte cap
* `redact.py` — secret/PII redactor on `error_excerpt` (re-uses 1.17's redaction patterns; lift to `_shared/secrets.py` deferred — see [[project-post-session-state-2026-05-20-evening]])
* `tests/` — split per cap

### Stub `well_known_paths` (`apps/stubs/well_known_paths/`)

* `__init__.py` — fires `@register("1.20")`, `@register("1.21")`, `@register("1.22")`, `@register("1.23")`, `@register("1.24")`, `@register("1.25")` on import (one runner registered six times, same precedent as 1.10 absorbing 1.18 — each spec ID maps to a family slice)
* `families.py` — Family enum (`env` / `git` / `config_files` / `logs` / `backup_archives` / `db_dumps`) + per-family default candidate-path list + per-family `Signature` set
* `candidates.py` — candidate-path resolver (default + scope-bounded overrides)
* `soft_404.py` — NEW: per-host soft-404 baseline detector (probe a known-nonexistent path, hash response shape, reject candidates that match)
* `fetcher.py` — bounded GET; redirect policy from shared HTTP; byte cap; binary-magic content-type override
* `classify.py` — per-family Verdict resolver (status + content-type + signature → high/medium/low/none)
* `runner.py` — orchestrates: soft-404 prelude → per-family candidate iteration → fetch → classify → persist
* `redact.py` — family-aware redaction (env values, .git pack data, log timestamps + IP addresses, SQL dump literals)
* `tests/` — split per cap, one test module per family + one shared-controls module

## TDD slices

Stack ordering: `feat/em-backend-1.19-sql-orm-errors` → `feat/em-backend-well-known-paths` (each branch one stub per [[project-stacked-branch-convention]]).

### Slice 19-A — `sql_orm_errors` signatures + matcher

1. `test_signatures.py` failing → assert each DB/ORM family has a typed `Signature` row with non-empty regex + named groups for `table`, `column`, `query_fragment`, `path` where present.
2. `signals.py`: `find_strongest_signal(body: bytes) -> Optional[Match]` returns the highest-priority match, or `None`. Tests cover one positive + one negative per family.
3. /simplify round 1, commit.

### Slice 19-B — classifier + Verdict ladder

1. `test_classify.py` failing → `classify(status, headers, body) -> Verdict` returns `{confidence: high|medium|low|none, signal_kind, framework_hints, error_excerpt}`. Ladder: strong signal → high; framework_hint + error_status (≥400) → medium; weak signal alone → low; nothing → none.
2. Negative grid: HTTP 200 with no error language → none; RFC 7807 problem+json with `detail: "internal error"` and no stack → none; server header alone → none.
3. /simplify round 1, commit.

### Slice 19-C — runner + persistence

1. `test_runner.py` failing → runner pulls candidate URLs from `target.recent_urls`, fetches with bounded client, classifies, writes one `Evidence` row per candidate + one `Finding` per high/medium verdict.
2. Findings: `category=sql_orm_errors.<family>` (postgres / mysql / sqlalchemy / etc.), `data={signal_kind, framework_hints[], error_excerpt_redacted}`, `confidence` from the ladder.
3. /simplify round 1, commit.

### Slice 19-D — spec-review pass + commit

1. Read `19-sql-orm-errors.md` end-to-end. Audit detection coverage, persistence contract, pass/fail assertions, acceptance criteria per [[feedback-spec-review-after-stub]].
2. Write report at `docs/superpowers/spec-reviews/2026-05-21-stub-1.19-sql-orm-errors.md`. Open follow-ups for any deferred coverage.
3. Commit. Flip 1.19 spec frontmatter `status: pending → done`. Regenerate PROGRESS.md.

### Slice WKP-A — `well_known_paths` families + signatures + soft-404 baseline

1. `test_families.py` failing → each `Family` enum value has a default candidate-path list (≥10 paths per family; env spec lists 20+) and a signature set.
2. `test_soft_404.py` failing → `baseline_for(target) -> SoftFootprint` probes one definite-nonexistent path (`/__definitely_not_a_real_path__<rand>`), hashes status + content-length-bucket + body-prefix, caches per target.
3. `matches_soft_404(response, footprint) -> bool` rejects candidates that match.
4. /simplify round 1, commit.

### Slice WKP-B — fetcher + per-family classifier

1. `test_fetcher.py` failing → bounded GET with shared client; redirect off; max_bytes from spec (env: 65536; archives: read magic-byte prefix only).
2. `test_classify.py` failing → per-family Verdict: family-specific status guard + content-type guard + signature match → high/medium/low/none. Negative grid: 404 → none; 200 SPA-shaped → soft-404 reject; archive with mismatched magic bytes → low.
3. /simplify round 1, commit.

### Slice WKP-C — runner + per-family persistence

1. `test_runner.py` failing → soft-404 prelude → per-family candidate iteration → fetch → classify → persist.
2. Findings: `category=well_known_paths.<family>` (env / git / config_files / logs / backup_archives / db_dumps), `data={family, candidate_path, signal_kind, redacted_excerpt}`, `confidence` from family classifier. Per-family scoring is preserved.
3. Redaction: env values redacted to `<KEY>=<REDACTED>` while preserving key names; `.git` pack data → `<binary-redacted bytes=N>`; logs → timestamps preserved, IPs/emails redacted; SQL dumps → CREATE TABLE preserved, INSERT VALUES redacted; archives → magic-byte preserved, content omitted.
4. /simplify round 1, commit.

### Slice WKP-D — frontmatter closures + spec-review

1. Flip spec frontmatter to `status: done` on 1.20, 1.21, 1.22, 1.23, 1.24, 1.25. Add closure note in each body pointing to `well_known_paths` stub (same template as 1.18 closure).
2. Regenerate PROGRESS.md (Overall: 5/278 → 11/278 done).
3. Spec-review pass: audit `well_known_paths` against each of the 6 specs. Report at `docs/superpowers/spec-reviews/2026-05-21-stub-well-known-paths.md`.
4. Commit.

## Persistence wiring

* Uses existing `Evidence` + `Finding` shapes from `apps/findings/models.py` (unchanged).
* `Finding.category`: `sql_orm_errors.<db_family>` for 1.19 / `well_known_paths.<family>` for WKP.
* `Finding.data` is family-specific JSON; frontend tolerates additive keys per [[project-merge-coordination]] rule (2). No cross-tier announcement needed.
* `Event.log()` emits one row per scan-run state change in the same transaction per [[project-event-log-medium-done-well]]. New event types: `FINDING_CREATED` (already exists), reuse.

## Verification (Phase 1 closed when all hold)

* `pytest backend/apps/stubs/sql_orm_errors backend/apps/stubs/well_known_paths` → all green, 100% line + branch coverage on stub production code.
* `pytest backend/` → full suite green (≥ 1400 + new tests).
* Spec-review reports committed at `docs/superpowers/spec-reviews/2026-05-21-stub-1.19-*.md` + `2026-05-21-stub-well-known-paths.md`.
* PROGRESS.md regenerated, Phase 1 specs `25/25 done`.
* All touched files ≤ 200 lines per [[feedback-strict-size-cap]].
* /simplify clean on each stub.

## Merge gate (per [[feedback-merge-heuristic]])

Apply heuristic at end of stack: phase boundary ✅, depth ≥ 3-5 ✅, 100% coverage ✅, spec-review closed ✅, no in-flight FU ✅ — squash-merge `feat/em-backend-well-known-paths` tip into main, then ping em-frontend per [[project-merge-coordination]] rule (3) — file-tree-overlap check first.

## Out of scope (tracked, deferred)

* `_shared/http.py` lift across 16+ fetchers (Phase-1-close shared lift, pre-existing follow-up).
* `_shared/secrets.py` lift between 1.15/1.17/1.19/WKP redactors (pre-existing follow-up).
* `_shared/evidence.py` lift for `save_response_evidence` (pre-existing).
* `_shared/soft_404.py` — only `well_known_paths` needs it today; lift when a second consumer arrives.
* Crawler-driven candidate URL discovery beyond `target.recent_urls` for 1.19 (depends on Phase 2 crawler MVP).
* Authenticated-context probes for 1.20–1.25 (deferred until Phase 2 auth state machine).
