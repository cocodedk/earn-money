# Slice WKP-A — `well_known_paths` families + signatures + soft-404 + apps.py wiring

Stack: `feat/em-backend-well-known-paths` stacked on the 1.19 stub tip. Pre-requisite: [`04b-slice-WKP-AUDIT-spec-review-first.md`](04b-slice-WKP-AUDIT-spec-review-first.md) committed first.

1. `test_families.py` failing → each `Family` enum value has a default candidate-path list (≥10 paths per family; env spec lists 20+), a signature set, and a severity hint (env: high; git: high; logs: medium; config_files: medium; backup_archives: medium; db_dumps: high).
2. `test_soft_404.py` failing → `baseline_for(target) -> SoftFootprint` probes one definite-nonexistent path (`/__definitely_not_a_real_path__<rand>`), hashes `(status, content-length-bucket, body-prefix-256)`, caches per `target`.
3. `matches_soft_404(response, footprint) -> bool` rejects candidates that match.
4. Update `backend/apps/stubs/apps.py` `ready()` to add `from . import well_known_paths  # noqa: F401  registers "1.20" (absorbs 1.21-1.25)`. Single `@register("1.20")` — same precedent as `debug_pages` registering once for 1.10 (which also covers 1.18). Assert via test that `get_registry()` has "1.20" but NOT "1.21".."1.25" — those are absorbed via spec-closure, not via additional registrations.
5. /simplify round 1, commit. Commit subject: `feat(stubs): well_known_paths families + signatures + soft-404 + apps.py wiring`.
