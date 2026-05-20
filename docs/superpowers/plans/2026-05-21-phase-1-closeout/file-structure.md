# File structure to create

## Stub 1.19 (`apps/stubs/sql_orm_errors/`)

* `__init__.py` — fires `@register("1.19")` on import.
* `apps.py` wiring — `backend/apps/stubs/apps.py` `ready()` must add `from . import sql_orm_errors`. Tracked as an explicit step in slice 19-B.
* `signatures.py` — Signature NamedTuple + per-DB/ORM regex set (PostgreSQL, MySQL, MSSQL, Oracle, SQLite, Django ORM, SQLAlchemy, Hibernate, ActiveRecord, Sequel, MongoDB error shapes) + severity hint per family (medium default; high for SQL fragment + table name disclosure).
* `signals.py` — matcher (regex search + named-group extraction).
* `classify.py` — Verdict NamedTuple → confidence ladder (`strong signal → high`, `framework_hint + error_status → medium`, `weak signal alone → low → reject`).
* `runner.py` — `run(scan_run, target_run) -> None` mirroring 1.16/1.17; iterates candidate URLs from `target.base_url` + prior-runner evidence (full crawler integration deferred — see [`out-of-scope.md`](out-of-scope.md)); fetches, classifies, **redacts**, persists. Dedup key: `(target_id, signal_kind, fingerprint(error_excerpt_redacted))` — re-detection → `confirmed`; disappearance → `stale`.
* `fetcher.py` — per-stub bounded GET (1.16/1.17 `fetcher.py` pattern; `_shared/http.py` lift deferred); same-origin redirect policy (one hop, stay on origin); byte cap.
* `redact.py` — secret/PII redactor on `error_excerpt` (re-uses 1.17's redaction patterns; lift to `_shared/secrets.py` deferred — see [[project-post-session-state-2026-05-20-evening]]). Wired BEFORE persistence.
* `tests/` — split per cap. Positive grid per DB/ORM family + negative grid (HTTP 200 no error language; RFC 7807; server-header alone; redacted excerpt round-trip; redirect to login/WAF; timeout/TLS; dedup-stale).

## Stub `well_known_paths` (`apps/stubs/well_known_paths/`)

* `__init__.py` — fires `@register("1.20")` ONCE on import (mirrors `debug_pages` precedent: stub 1.10 owns the absorbed coverage of 1.18 via a single `@register("1.10")`, not six). The runner probes every family in one pass per scan. Specs 1.21–1.25 are closed via frontmatter + closure-note (slice WKP-D), NOT via additional `@register` decorators.
* `apps.py` wiring — `backend/apps/stubs/apps.py` `ready()` must add `from . import well_known_paths` (and `from . import sql_orm_errors`). Without this, `@register` never fires and the runner is never dispatched. Tracked as explicit steps in slice WKP-A (for well_known_paths) and slice 19-B (for sql_orm_errors).
* `families.py` — Family enum (`env` / `git` / `config_files` / `logs` / `backup_archives` / `db_dumps`) + per-family default candidate-path list + per-family `Signature` set + per-family severity hint (env: high; git: high; logs: medium; config_files: medium; backup_archives: medium; db_dumps: high).
* `candidates.py` — candidate-path resolver (default + scope-bounded overrides).
* `soft_404.py` — NEW: per-host soft-404 baseline detector (probe a known-nonexistent path, hash response shape, reject candidates that match). Baseline cached per `target` for the scan lifetime so we don't re-probe.
* `fetcher.py` — per-stub bounded fetcher (1.16/1.17 `fetcher.py` pattern; `_shared/http.py` lift deferred). **HEAD-first** probe + 200/206 GET with **`Range: bytes=0-65535`** (or smaller per family) for archives + db_dumps + logs per specs 21/23/24/25 ("do not download full files"). Same-origin redirect policy (one hop, must stay on `target.base_url`'s origin). Byte cap enforced; binary-magic content-type override (zip / gzip / sqlite / tar magic).
* `classify.py` — per-family `Verdict` NamedTuple resolver (status + content-type + signature + magic-byte → confidence high/medium/low/none + severity).
* `runner.py` — orchestrates: soft-404 baseline → per-family candidate iteration → HEAD → conditional GET-with-Range → classify → **redact** → persist. Dedup key: `(target_id, family, candidate_path, signal_kind)` — re-running the scan flips re-detected findings to `confirmed`; disappearing findings flip to `stale`.
* `redact.py` — family-aware redaction (see WKP-C for full pattern table). Wired BEFORE persistence — never persist raw excerpts.
* `tests/` — split per cap. Per-family positive + per-family soft-404 / redirect-to-login / binary-magic-mismatch / Range-refusal / timeout / TLS-error / dedup-stale negative grid (see WKP-B + WKP-C).
