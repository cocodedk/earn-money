# Slice WKP-AUDIT — spec audit BEFORE implementation (6 specs)

Same principle as [`00-slice-19-AUDIT-spec-review-first.md`](00-slice-19-AUDIT-spec-review-first.md): read every spec FIRST. WKP absorbs six specs, so the audit reads six specs in one pass and produces one consolidated audit report.

1. Read specs `20-env.md`, `21-git.md`, `22-config-files.md`, `23-logs.md`, `24-backup-archives.md`, `25-exported-database-files.md` end-to-end. Cross-spec contract reconciliation — the six specs may disagree on edge cases (byte caps, redirect policy, HEAD-vs-GET); resolve those by picking the most restrictive value across the six and noting deviations.
2. Extract per-family: candidate paths, mandated `Signature` shape, mandated `Finding.data` keys, severity hint, must-not assertions, status vocabulary mapping.
3. Surface specs 21/23/24/25's HEAD-first / Range / "do not download full files" requirement — this shapes `fetcher.py` design from slice WKP-B onward.
4. Write consolidated audit at `docs/superpowers/spec-reviews/2026-05-21-stub-well-known-paths-pre.md`. One section per family + one cross-family section listing the resolved conflicts.
5. Commit. Commit subject: `docs(stub-reviews): well_known_paths pre-implementation spec audit (6 specs)`.
