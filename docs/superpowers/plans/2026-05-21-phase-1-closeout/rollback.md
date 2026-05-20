# Rollback plan

If a slice introduces a regression or any post-merge issue surfaces, revert as follows. Per [[feedback-merge-heuristic]] / [[project-stacked-branch-convention]]: most reverts are per-slice commits; the whole stack reverts via one squash revert if needed.

## Per-slice revert (preferred)

* **Runner code (sql_orm_errors / well_known_paths)** → `git revert <slice-commit-sha>`. Re-runs of the registry won't pick up the unregistered runner, so the kill-switch is effectively the apps.py import.
* **Runner registration** → comment out the corresponding `from . import sql_orm_errors` / `from . import well_known_paths` line in `backend/apps/stubs/apps.py` ready() to disable the stub without code changes. Re-enabling = uncomment.
* **Spec frontmatter** (`status: done → pending`) → re-edit the frontmatter back to `pending`, drop the closure note, then `python scripts/cookbook_progress.py` (run from canonical venv).
* **PROGRESS.md** → re-run `python scripts/cookbook_progress.py` after the frontmatter revert.
* **`FINDING_CREATED` event type** → revert the row in `backend/apps/events/types.py`. Owner: slice WKP-A (single site for the enum addition, per [`tasks/05-slice-WKP-A-families-signatures-soft404.md`](tasks/05-slice-WKP-A-families-signatures-soft404.md) step 5). NB: any emitted events with this type need migration handling if they've reached the DB (low probability before merge).

## Whole-stack revert

* `git revert <main-squash-commit-sha>` on `main`. Reverts the whole Phase 1 closeout in one commit. PROGRESS.md regenerates automatically on next bootstrap run.
* Notify em-frontend via chat per [[project-merge-coordination]] rule (3).
* No DB migrations to roll back (no new models).

## Cannot-rollback items

* Findings emitted in a real production scan run before revert: those rows stay in the DB as historical evidence. Operator decision per finding whether to manually flip to `rejected`.
* Spec-review markdown reports under `docs/superpowers/spec-reviews/` are append-only docs; deletion would lose audit history. Mark as superseded instead.
