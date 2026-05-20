# Slice WKP-B — fetcher (HEAD-first + Range) + per-family classifier

Specs 21 / 23 / 24 / 25 mandate "do not download full files" — fetcher uses HEAD-first probes and `Range`-bounded GETs.

1. `test_fetcher.py` failing → per-stub bounded fetcher (1.16/1.17 `fetcher.py` pattern; `_shared/http.py` lift deferred). Flow:
   - **HEAD** the candidate path first. If HEAD returns 405/501 (method unsupported), fall back to GET with `Range: bytes=0-65535`.
   - **GET-with-Range** for archives / db_dumps / logs (caps: archives 4096 bytes prefix for magic byte read; db_dumps 65536; logs 65536). Env / git / config_files: full GET with hard 65536 cap.
   - **Same-origin redirect** policy: at most one hop, must stay on `target.base_url`'s origin (scheme + host + port match). Out-of-origin redirect → reject the candidate (no Finding).
   - **Soft-404 reject**: matches against the cached `SoftFootprint` from slice WKP-A.
   - **No follow on `Content-Length` > cap when no Range support** (server refused Range, full body too large): reject the candidate, log an event, never persist.
2. `test_classify.py` failing → per-family `Verdict` NamedTuple: family-specific status guard + content-type guard + signature match + magic-byte check → confidence high/medium/low/none + severity from family hint.
3. Negative grid (in test_classify + test_fetcher): 404 → none; 200 SPA-shaped → soft-404 reject; archive with mismatched magic bytes → low (mismatch logged); HEAD timeout → reject + event; TLS handshake error → reject + event; Range refused + body > cap → reject + event; cross-origin redirect → reject + event; login/WAF redirect (3xx → 200 with login form signature) → reject + event.
4. /simplify round 1, commit. Commit subject: `feat(stubs): well_known_paths HEAD-first + Range fetcher + per-family classifier`.
