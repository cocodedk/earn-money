# Slice 0 — AUDIT (pre-implementation)

Stack: `feat/em-backend-scope-enforcement` off `feat/em-backend-well-known-paths` tip per [[project-stacked-branch-convention]].

1. Read `archive/v1/src/earn_money/{scope.py,flags.py,config.py}` end-to-end. Distill the wire format + matcher semantics + flag-file semantics.
2. Read CLAUDE.md "Hard rules" section + "Three-tier program policy" + "Per-program Rules of Engagement" + "Kill-switch". Pin the runtime contract.
3. Inventory v2 integration points before coding: scan-run creation/start path, runner entrypoints, every Phase 1 HTTP call site, existing cache/Redis support, event enum/model behavior, and docker-compose mounts. Record the authoritative list of stubs with standalone runners; do not rely only on the hardcoded list in slice G.
4. Confirm `programs/hackerone/algolia/{scope.md,roe.md}` exists and capture exact YAML frontmatter fields, allowed values, and defaults. If the files are missing, stop before slice A and ask the operator whether to copy from v1 or create fresh fixtures.
5. Write audit at `docs/superpowers/spec-reviews/2026-05-21-scope-enforcement-pre.md` listing: wire formats, must-not assertions, runtime contracts, integration points with existing v2 backend, runner inventory, and cache/rate-limit decision.
6. Commit: `docs(stub-reviews): scope-enforcement pre-implementation audit`.
