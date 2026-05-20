# Merge gate

Per [[feedback-merge-heuristic]].

Apply heuristic at end of stack: phase boundary ✅, depth ≥ 3-5 ✅, 100% coverage ✅, spec-review closed ✅, no in-flight FU ✅ — squash-merge `feat/em-backend-well-known-paths` tip into main, then ping em-frontend per [[project-merge-coordination]] rule (3) — _"post-merge ping + conditional rebase: only rebase if file-tree overlap exists between the merged stack and the receiver's open work"_. File-tree-overlap check first; expect no-op (backend↔frontend trees are disjoint today).

**Rollback strategy** if anything regresses post-merge: see [`rollback.md`](rollback.md). Most likely path: comment out the apps.py import line for the offending stub (instant kill-switch), then decide whether to `git revert` the squash commit. No DB migrations need rolling back.

**Cross-tier contract pre-announce** is NOT required for this merge (`Finding.data` additions are additive per [[project-merge-coordination]] rule (2)); the post-merge ping in rule (3) is sufficient.
