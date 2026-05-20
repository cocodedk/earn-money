# Rollback — Phase 2

## Per-program kill switch

Per-program freeze via `programs/<platform>/<slug>/FROZEN` ALREADY
covers every Phase 2 stub via the existing `is_program_frozen` check
inside `guard()`. To halt all Phase 2 activity against one program:

```
touch programs/hackerone/<slug>/FROZEN
```

Next runner invocation against that program raises `ProgramFrozen`
and the stub exits immediately.

## Global kill switch

`rm flags/RECON_ENABLED` halts EVERY active stub (Phase 1 + Phase 2)
on the next invocation. Same mechanism that worked for Phase 1's
algolia smoke.

## Per-Phase-2-feature switch

`apps/programs/roe.py` adds five `allow_*_probes` knobs. To halt one
Phase 2 surface without touching the rest:

```yaml
# In programs/<platform>/<slug>/roe.md frontmatter
allow_active_login_probes: false
```

Reload happens on the next `find_for_host` (which re-reads roe.md on
mtime change). No process restart needed.

## Revert the whole phase

If Phase 2 needs to revert post-merge:

```
git revert -m 1 <squash-merge-sha>
git push origin main
```

The merge commit's parent links let `revert -m 1` undo the entire
Phase 2 stack atomically. Phase 1 stubs continue to work.

## Recovering from a half-shipped stub

If a single Phase 2 stub causes problems on `main`:

1. Touch a per-program FROZEN flag (fastest — instant halt for the
   affected programs).
2. Land a follow-up PR that unregisters the stub (`@guarded_runner`
   line commented out, runner module imports kept for any shared
   helpers used by other stubs).
3. Investigate + fix in a fresh slice + re-enable.

## What this is NOT

* This is not a backout for code already in the wild. By the time a
  stub is on `main`, it's been exercised against fixture targets +
  spec-reviewed + /simplify-checked. The rollback paths above are
  for unanticipated production failures, not routine reverts.
