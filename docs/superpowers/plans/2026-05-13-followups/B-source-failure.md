# B — Investigate + fix nuclei source failure

**Problem:** Today's nuclei run on `hackerone/security` completed with
`status='partial'`, `source_failures=1`. One of the batches errored.
Cause unknown — could be transient (rate limit, network blip) or
systematic (bad command construction, template parse error).

**Solution:** Read the stderr artifact, identify root cause, decide
between (a) document as transient and move on, (b) fix a real bug.

## Steps

- [ ] **1. Pull artifacts from the VPS run**

```bash
# Pick the most-recently-modified artifact dir (mtime-sorted, not lexicographic)
DIR=$(ssh recon-vps "ls -1dt /opt/earn-money/recon/outputs/hackerone/security/nuclei/2026-05-13/*/ | head -1")
ssh recon-vps "ls -la $DIR"
ssh recon-vps "cat $DIR/stderr.txt"
ssh recon-vps "cat $DIR/manifest.json"
```

- [ ] **2. Diagnose**

Look for:
- Per-batch return code in `manifest.json` (or whatever the runner records).
- Per-batch stderr — the failing batch usually says *why* in its tail
  (`Error: ...`, `connection refused`, `template not found`, `panic: ...`).
- Whether the batch hit `-rl 10` (rate-limit) ceiling.

Three triage outcomes:

  - **Transient (network / rate-limit / target 5xx):** add a one-line note to the gap log and move on. Document for future reference but no code change.
  - **Systematic (bad command / parser / panic):** Phase 3 — write a failing test and fix.
  - **Inconclusive:** add a slightly more verbose error logger to `batch.py` (one-liner: include the offending command + first 200 chars of stderr in `error_summary`). Commit + coderabbit.

- [ ] **3. If transient:** append a "Cycle 1 source failure: <cause>"
  paragraph to `ops/engagements/2026-05-13-first-real-target.md`.
  Commit `docs(ops): identify cycle-1 source failure as <cause>`.

- [ ] **4. If systematic:** write a failing test reproducing the bug,
  fix it in the minimal place (likely `recon/nuclei_tool.py` or
  `runners/batch.py`), `make smoke` green, commit
  `fix(<area>): <one-line>`. CodeRabbit on the commit.

- [ ] **5. If inconclusive:** make `batch.py` log the first 200 chars
  of failing stderr into `error_summary`. Write a test that the
  failure path includes the new substring. Commit
  `feat(batch): include stderr tail in error_summary on per-batch failure`.
  CodeRabbit.

- [ ] **6. Final commit:** if any non-trivial output, also update the
  engagement gap log with what was found.
