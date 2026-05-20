# Slice G — Wire remaining stubs through `enforce_scope`

Slice E already wired stub 1.20 (well_known_paths) as the canary. This slice covers the remaining Phase 1 stubs.

1. Start from the runner/HTTP inventory written in Slice 0. The expected standalone-runner set is 1.1 / 1.2 / 1.3 / 1.4 / 1.5 / 1.6 / 1.7 / 1.8 / 1.9 / 1.10 / 1.11 / 1.12 / 1.13 / 1.14 / 1.15 / 1.16 / 1.17 / 1.19; if AUDIT finds a different set, update this file and tests in the same slice before wiring.
2. `test_runner_scope.py` per stub-with-its-own-runner → asserts an out-of-scope candidate URL emits `OUT_OF_SCOPE_REJECTED` instead of issuing a real HTTP. Specs 1.18 + 1.21–1.25 have NO standalone runner only if confirmed by AUDIT (absorbed by stubs 1.10 + well_known_paths respectively); their coverage falls out of the absorbing stub's fetcher.
3. Migration: each fetcher's GET/HEAD call site adds `require_recon_enabled`, FROZEN re-check, `enforce_scope`, and rate-limit in that order before network I/O. Queued work must stop if the flag was removed after scan-run creation.
4. Add a static or grep-based regression test over the inventory so future HTTP call sites cannot bypass `_shared/http.py` / `enforce_scope` silently.
5. Commit: `feat(stubs): wire all remaining Phase 1 stubs through scope enforcement`.
