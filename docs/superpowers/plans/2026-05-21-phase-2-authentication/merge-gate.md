# Merge gate — Phase 2 squash-merge

> One squash-merge of `feat/em-backend-phase-2` (the stack tip) lands the
> whole Phase 2 stack on `main`. Operator-triggered, not auto.

## Required before pushing to remote

* `git log origin/main..feat/em-backend-phase-2` lists every Phase 2
  commit. Operator reviews the SHA list before authorising push.
* All 11 verification.md gates green (slice 24 closeout report).
* No uncommitted files in the working tree.
* No `.env` / `flags/RECON_ENABLED` / `identity/` artifacts staged.
* `git status` clean.
* Frontend tip merged in (per the operator-em-frontend coordination
  pattern from scope-enforcement).

## Push command

```
git push origin feat/em-backend-phase-2
gh pr create --base main --head feat/em-backend-phase-2 \
  --title "feat: Phase 2 authentication stubs (2.1-2.22)" \
  --body-file docs/superpowers/spec-reviews/2026-05-21-phase-2-authentication.md
```

The PR body links the Phase 2 spec-review which transitively links
each per-stub review.

## Squash-merge rules

* Operator does the squash-merge, not the bot.
* Squash commit title: `feat: Phase 2 authentication stubs (2.1-2.22)`.
* Squash commit body: copy of the aggregate spec-review.
* Branch deleted after merge.
* `main` becomes the new base for Phase 3.

## What this protects against

* Half-merged Phase 2 state — if any stub fails verification it stays
  out of the merge entirely.
* Cross-tier desync — em-frontend coordinates their UI changes against
  the SAME stack tip, so the merge brings frontend + backend together.
* Re-merge churn — one squash, one diff, one PR for code review.

## Rollback

See `rollback.md`.
