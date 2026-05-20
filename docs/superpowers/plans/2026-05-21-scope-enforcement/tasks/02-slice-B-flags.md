# Slice B — `flags.py` + RECON_ENABLED + per-program freeze

1. `test_flags.py` failing → `require_recon_enabled(path=settings.RECON_ENABLED_PATH)` raises `ReconDisabled` when the flag is absent or is a directory; passes only when the path is an existing regular file. `is_program_frozen(platform, slug)` returns True when `settings.PROGRAMS_ROOT/<platform>/<slug>/FROZEN` exists.
2. `flags.py` per archived v1, but path inputs come from settings so containers can mount `/flags/RECON_ENABLED` while local dev can use the repo-root file.
3. Add `RECON_ENABLED_PATH` settings coverage and docker-compose notes from [`../file-structure.md`](../file-structure.md); do not use a single-file bind mount for an optional flag.
4. Commit: `feat(programs): RECON_ENABLED kill-switch + per-program freeze`.
