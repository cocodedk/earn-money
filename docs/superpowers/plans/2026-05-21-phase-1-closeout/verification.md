# Verification (Phase 1 closed when all hold)

* `pytest backend/apps/stubs/sql_orm_errors backend/apps/stubs/well_known_paths` → all green, 100% line + branch coverage on stub production code.
* `pytest backend/` → full suite green (≥ 1400 + new tests).
* Spec-review reports committed: pre-implementation audits at `docs/superpowers/spec-reviews/2026-05-21-stub-1.19-sql-orm-errors-pre.md` + `2026-05-21-stub-well-known-paths-pre.md`; post-implementation audits at `docs/superpowers/spec-reviews/2026-05-21-stub-1.19-sql-orm-errors.md` + `2026-05-21-stub-well-known-paths.md`.
* PROGRESS.md regenerated. This stack flips 1.19 + 1.20–1.25 to `status: done` (7 specs), taking total done from 5/278 → 12/278. Phase 1 frontmatter reconciliation for the 13 other code-shipped-but-pending stubs (1.1–1.9 + 1.14–1.17) is a pre-existing follow-up, not part of this closeout — tracked in `out-of-scope.md`.
* All touched files ≤ 200 lines per [[feedback-strict-size-cap]].
* /simplify clean on each stub.
* `apps.py` wiring asserted by test: `get_registry()` contains "1.19" and "1.20" after `apps.ready()`; does NOT contain "1.21"–"1.25" (WKP absorbs those, doesn't register them).
* `FINDING_CREATED` enum value present in `backend/apps/events/types.py`; asserted by test.
* Per-stub test grids cover the full negative matrix per slice WKP-B + WKP-C (soft-404, login/WAF redirect, binary-magic mismatch, timeout, TLS, Range refusal, cross-origin redirect, dedup, stale). 1.19 grid covers redirect/timeout/TLS/dedup/stale.
* No persisted `Finding.data.redacted_excerpt` contains raw secrets — asserted by a redaction round-trip test in WKP-C.
* Rollback plan documented in [`rollback.md`](rollback.md) and dry-run validated (apps.py comment-out path).
