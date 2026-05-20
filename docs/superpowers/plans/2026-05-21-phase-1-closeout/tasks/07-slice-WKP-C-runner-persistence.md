# Slice WKP-C — runner + redaction + per-family persistence

Redaction is wired BEFORE persistence in this single slice (codex Stage 5 finding: never persist raw `.env` / `.git` pack / logs / SQL dumps / config / archive content). The previously-planned WKP-C2 split into a "redaction-after-runner" slice is **dropped** — the identity passthrough commit was unsafe.

1. `test_redact.py` failing → one positive + one negative test per family redactor (six families). Family strategies:
   - **env**: values → `<KEY>=<REDACTED>` while preserving key names.
   - **git**: pack data + object blobs → `<binary-redacted bytes=N>`; refs/HEAD ASCII headers preserved.
   - **logs**: ISO-8601 timestamps preserved; IPv4 + IPv6 + RFC-5322 emails → `<IP>` / `<EMAIL>`. No JWT/bearer leak.
   - **SQL dumps**: `CREATE TABLE` verbatim; `INSERT INTO <tbl> (<cols>) VALUES (...)` → keeps table + column list, redacts value tuples to `(<REDACTED>)`.
   - **archives**: magic-byte prefix preserved, body → `<binary-redacted bytes=N>`.
   - **config_files**: JSON/YAML keys preserved; values matching the 1.17 secret/PII regex set → `<REDACTED>`.
2. `test_runner.py` failing → soft-404 prelude → per-family candidate iteration → HEAD → GET-with-Range → classify → **redact via `redact.py`** → persist.
3. Findings: `category=well_known_paths.<family>` (env / git / config_files / logs / backup_archives / db_dumps), `data={family, candidate_path, signal_kind, redacted_excerpt, severity}`, `confidence` from family classifier. Per-family scoring is preserved. **Status vocabulary**: new finding → `candidate`; re-detection with matching dedup key → `confirmed`; disappearance on subsequent scan → `stale`. **Dedup key**: `(target_id, family, candidate_path, signal_kind)`. **Severity**: from family hint.
4. Negative tests (added to `test_runner.py`): redirect to login/WAF → no Finding + event; timeout → no Finding + event; TLS error → no Finding + event; Range refused with body > cap → no Finding + event; same-origin policy violated → no Finding + event; re-run with identical evidence → status flip to `confirmed` (no duplicate Finding row); re-run after fix → status flip to `stale`; assert no raw secret in any persisted `Finding.data.redacted_excerpt`.
5. /simplify round 1, commit. Commit subject: `feat(stubs): well_known_paths runner + redaction + per-family persistence`.
