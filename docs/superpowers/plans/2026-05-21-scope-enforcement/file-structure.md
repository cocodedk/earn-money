# File structure to create

* `backend/apps/programs/` — new Django app.
  - `apps.py` — `ProgramsConfig`.
  - `loader.py` — `Program` dataclass + `ProgramRegistry` reading `programs/<platform>/<slug>/{scope.md,roe.md}`. Mtime cache.
  - `scope.py` — `Scope` dataclass + `matches_scope(host, in_scope, out_of_scope) -> bool` (wildcard suffix logic).
  - `flags.py` — `require_recon_enabled()` / `is_program_frozen()` using exceptions imported from `exceptions.py`.
  - `roe.py` — `RoE` dataclass with `max_requests_per_second`, `dos_authorized`, etc.
  - `exceptions.py` — `InvalidScope`, `OutOfScope`, `ManualOnly`, `AmbiguousPolicy`, `AmbiguousProgram`, `ReconDisabled`, `ProgramFrozen` shared by loader, scans, and stubs.
  - `rate_limit.py` — per-program token-bucket honoring `roe.max_requests_per_second`.
  - `tests/` — split per cap.
* `backend/apps/scans/models.py` — extend `ScanRun.start()` (or `create_scan_run` view-helper) with the pre-flight scope check.
* `backend/apps/stubs/_shared/scope_check.py` — NEW: `enforce_scope(target, candidate_url, program, *, scan_run=None, stub_id=None)` for fetcher-level enforcement. Each stub's fetcher calls this before issuing any request.
* `backend/apps/events/types.py` — add `OUT_OF_SCOPE_REJECTED = "scan.out_of_scope_rejected"`.
* `backend/config/settings.py` — `PROGRAMS_ROOT = Path(os.environ.get("PROGRAMS_ROOT", "/programs"))` and `RECON_ENABLED_PATH = Path(os.environ.get("RECON_ENABLED_PATH", "/flags/RECON_ENABLED"))` (container defaults; local-dev override via env var). Wired into the loader/flags modules in slices B+C.
* `docker-compose.yml` — mount `./programs:/programs:ro` on `backend` + `worker`. Mount the directory containing the optional flag as `./:/flags:ro` or another stable host directory; do not bind-mount `./RECON_ENABLED` as a single file because Docker may create a directory when the file is absent.
