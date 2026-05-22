# Rollback

* **Emergency stop** → `rm RECON_ENABLED` at repo root. Every active stub refuses to start; already-running runners must re-check at runner entry and before each fetcher batch. This stops recon, it does not remove code.
* **Revert per-slice** → `git revert <sha>` in reverse slice order; tests catch regressions. If slice E generated a migration solely for event choices, revert that migration with the slice.
* **Whole-stack revert** → squash revert; programs/ directory + algolia files stay (data, not code). After revert, remove only transient local flag files created for smoke (`RECON_ENABLED`), never scope/RoE data.
