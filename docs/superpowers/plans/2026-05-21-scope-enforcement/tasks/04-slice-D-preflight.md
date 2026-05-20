# Slice D — Scan-run pre-flight scope check

1. `test_scan_run_preflight.py` failing → creating a ScanRun for a target whose host is in-scope on exactly one known program succeeds; out-of-scope refuses with `OutOfScope`; equal-specificity program match refuses with `AmbiguousProgram`; `manual-only` policy refuses with `ManualOnly`; `ambiguous` policy refuses with `AmbiguousPolicy` for active stubs; missing RECON_ENABLED refuses with `ReconDisabled`; program-FROZEN flag refuses with `ProgramFrozen` (from slice B).
2. Hook the check into `ScanRunViewSet.create()` (or `ScanRun.start()` action) before enqueueing any Celery task. API errors must be explicit 4xx responses and must not create a queued run.
3. Normalize target URLs before lookup: require `http` or `https`, reject hostless URLs, lower-case/IDNA the hostname, ignore ports, and pass only the host to `ProgramRegistry.find_for_host`.
4. Store/pass the resolved `Program` runtime context (`platform`, `slug`, `scope`, `roe`) into the runner payload used by slices E-G. Do not make fetchers re-resolve the target.
5. Commit: `feat(scans): pre-flight scope + RECON_ENABLED + FROZEN check on ScanRun creation`.
