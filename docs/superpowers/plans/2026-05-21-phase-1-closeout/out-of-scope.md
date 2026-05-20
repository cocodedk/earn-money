# Out of scope (tracked, deferred)

* `_shared/http.py` lift across 16+ fetchers (Phase-1-close shared lift, pre-existing follow-up).
* `_shared/secrets.py` lift between 1.15/1.17/1.19/WKP redactors (pre-existing follow-up).
* `_shared/evidence.py` lift for `save_response_evidence` (pre-existing).
* `_shared/soft_404.py` — only `well_known_paths` needs it today; lift when a second consumer arrives.
* Crawler-driven candidate URL discovery beyond `target.recent_urls` for 1.19 (depends on Phase 2 crawler MVP).
* Authenticated-context probes for 1.20–1.25 (deferred until Phase 2 auth state machine).
* Spec frontmatter reconciliation for 1.1–1.9 + 1.14–1.17 (13 specs) — all are code-shipped but frontmatter still `status: pending`. Reconcile in a follow-up so PROGRESS.md reflects ground truth before Phase 2 starts. Verified 2026-05-20 via `grep ^status: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/*.md`.
