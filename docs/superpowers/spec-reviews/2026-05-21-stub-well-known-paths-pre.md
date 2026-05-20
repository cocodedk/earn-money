# Stub `well_known_paths` — pre-implementation 6-spec consolidated audit

> Specs absorbed (per [[project-cookbook-frontmatter]] + 1.10→1.18 precedent):
> - 1.20 [`20-env.md`](../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/20-env.md) — 533 lines
> - 1.21 [`21-git.md`](../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/21-git.md) — 484 lines
> - 1.22 [`22-config-files.md`](../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/22-config-files.md) — 556 lines
> - 1.23 [`23-logs.md`](../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/23-logs.md) — 594 lines
> - 1.24 [`24-backup-archives.md`](../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/24-backup-archives.md) — 531 lines
> - 1.25 [`25-exported-database-files.md`](../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/25-exported-database-files.md) — 435 lines
> Plan slice: [`tasks/04b-slice-WKP-AUDIT-spec-review-first.md`](../plans/2026-05-21-phase-1-closeout/tasks/04b-slice-WKP-AUDIT-spec-review-first.md)
> Audit date: 2026-05-20

## Cross-spec contract resolution

All six specs share the same shape: GET a known path, validate response (status + content-type + body signature + magic bytes for binary families), classify confidence, persist Finding. Differences are per-family content rules. Resolved conflicts by picking the **most restrictive** per category:

| Cross-cutting | Resolution |
|---------------|------------|
| HTTP method | `HEAD` first (every spec), `GET` with `Range: bytes=0-N` only when HEAD ambiguous (specs 21/23/24/25 explicit; 20/22 don't forbid Range). |
| Max body bytes | `65536` for text families (env/git-text/config/logs); `4096` for archive/db_dump magic-byte prefix-only read (specs 24/25). |
| Redirect policy | Same-origin one-hop max (every spec). Out-of-origin redirect → reject candidate. |
| Soft-404 / SPA | Every spec requires soft-404 detection; lift to shared `soft_404.py` per the plan. |
| Severity ceiling | `info|low|medium`. Specs 20/21/25 mention `medium` for high-impact (env values, git pack data, raw db dump). Specs 22/23/24 allow `low`-default with `medium` lift when sensitive content visible. |
| Status vocabulary | `candidate | confirmed | rejected | stale` everywhere. |
| Dedup key | `(target_id, family, candidate_path, signal_kind)` consolidated across families. |
| AI involvement | `None` everywhere — deterministic only. |

## Per-family contract summary

### 1.20 env (`Family.env`)
- **Candidate paths:** 20+ `.env` variants under root + `/api/`, `/app/`, `/backend/`, `/config/`, `/server/`. See spec §Default candidate paths.
- **Detection:** Response body matches `KEY=VALUE` line pattern; presence of `DB_PASSWORD`, `STRIPE_KEY`, `AWS_*`, JWT secrets boosts confidence.
- **Severity hint:** high impact → `medium`. Default `low` if env file present but values blank.
- **Redaction:** Values → `<KEY>=<REDACTED>` while preserving key names.

### 1.21 git (`Family.git`)
- **Candidate paths:** `/.git/HEAD`, `/.git/config`, `/.git/index`, `/.git/objects/info/packs`, `/.git/refs/heads/*`, `/.gitignore` (per spec — exact list in spec §candidate_paths).
- **Detection:** ASCII control files contain known headers (`ref:`, `[remote `, etc.); binary objects pack magic.
- **Severity hint:** `medium` for binary pack data; `low` for HEAD/config without pack.
- **Redaction:** Pack/object bytes → `<binary-redacted bytes=N>`; refs/HEAD ASCII preserved.

### 1.22 config_files (`Family.config_files`)
- **Candidate paths:** `application.yml`, `application.properties`, `config.json`, `appsettings.json`, `web.config`, `docker-compose.yml`, `Dockerfile`, `kustomization.yaml`, `package.json`, `composer.json`, `bundle.json`, plus framework-specific (rails `database.yml`, django `settings.py`-style hint paths).
- **Detection:** Content-type alignment (JSON/YAML/XML) + family-specific key patterns (`spring.datasource.password`, `secrets:`, `aws:`, `database:`).
- **Severity hint:** `low` default; `medium` when secrets/credentials visible.
- **Redaction:** JSON/YAML keys preserved; values matching the 1.17 secret/PII regex set → `<REDACTED>`.

### 1.23 logs (`Family.logs`)
- **Candidate paths:** `/logs/`, `/log/`, `/app.log`, `/server.log`, `/access.log`, `/error.log`, `/debug.log`, `/laravel.log`, `/uwsgi.log`, `/nginx-error.log`. See spec §candidate_paths for full list.
- **Detection:** ASCII text + ISO-8601 / common-log-format / nginx combined-log timestamps + level tokens (INFO/WARN/ERROR).
- **Severity hint:** `low` if structured log only; `medium` when stack traces, IPs, emails, session tokens visible.
- **Redaction:** ISO-8601 timestamps preserved; IPv4 + IPv6 + RFC-5322 emails → `<IP>` / `<EMAIL>`. No JWT/bearer leak.

### 1.24 backup_archives (`Family.backup_archives`)
- **Candidate paths:** Per-extension patterns: `{stem}.zip`, `{stem}.tar.gz`, `{stem}.7z`, `{stem}.rar`, `.tbz2`, `.gz`, `.bz2`, `.xz`. Stems: `backup`, `archive`, `old`, `tmp`, `_private`, plus the target's host-derived stem.
- **Detection:** **Magic-byte prefix read only** (4096-byte Range). zip magic `PK\x03\x04`; gzip `\x1f\x8b`; tar mid-block `ustar`; 7z `7z\xbc\xaf\x27\x1c`; rar `Rar!\x1a`. Mismatch → low confidence.
- **Severity hint:** `medium` (archives often contain credentials).
- **Redaction:** Magic-byte prefix preserved, body → `<binary-redacted bytes=N>`. No content extraction.

### 1.25 db_dumps (`Family.db_dumps`)
- **Candidate paths:** `/db.sql`, `/backup.sql`, `/database.sql`, `/dump.sql`, `/{stem}.sql`, `.sqlite`, `.sqlite3`, `.db`, `.mdb`, plus per-DB extensions.
- **Detection:** SQL: `CREATE TABLE`, `INSERT INTO`, `-- Dump of database` headers; SQLite: `SQLite format 3\x00` magic; Access: `\x00\x01\x00\x00Standard Jet DB`.
- **Severity hint:** `medium` (data dumps are high-impact).
- **Redaction:** `CREATE TABLE` verbatim; `INSERT INTO <tbl> (<cols>) VALUES (...)` → keeps table + column list, redacts value tuples to `(<REDACTED>)`. SQLite/binary db files → magic preserved, body redacted.

## Shared types sufficiency

- `ScanTarget` + `Evidence` — sufficient. No new shared model needed.
- `Family` enum local to the stub (per spec — stub-specific).
- `Signature` NamedTuple — adapted from stub 1.19's; per-family pattern table.
- `SoftFootprint` NamedTuple — NEW shared-control helper at `apps/stubs/well_known_paths/soft_404.py`.

## Single-stub absorption rationale

Mirrors 1.10's absorption of 1.18: ONE `@register("1.20")` (spec 1.20 chosen as lowest-numbered owner), runner probes ALL 6 families in one pass. Specs 1.21–1.25 get the same closure treatment as 1.18 — `status: done` + closure note pointing to `well_known_paths` stub. Codex-blessed direction (2026-05-20 consult) citing identical core loop + shared safety controls (soft-404, byte caps, redirect policy, redaction).

## Must-not assertions (consolidated regression grid)

Cross-spec consolidation of `## Safety` § restrictions:

1. **No mutating HTTP methods** anywhere (PUT/PATCH/DELETE/POST forbidden). HEAD + GET only.
2. **No full-file downloads** for archives/db_dumps/logs > 65536 bytes (specs 21/23/24/25 explicit "do not download full files").
3. **No content extraction** from archives — magic-byte read only.
4. **No following of out-of-scope URLs** from disclosed file paths or remote URLs.
5. **No hostname-to-technology hard-coding** — detect from response evidence only.
6. **No LLM/AI calls** (AI involvement: None for all 6 specs).
7. **No retry after timeouts/TLS errors** beyond shared scanner policy.
8. **No persistence of cookies / auth headers / session tokens / API keys / DB passwords** in `Finding.data` snippets.
9. **No fuzzing** with wordlists; **no brute-force** of path variants beyond the per-family default list (≤spec.max_candidate_urls).
10. **No follow on Content-Length > cap** when server refuses Range — reject + Event + skip.
11. **No high/critical severity** emission from this check alone.
12. **No duplicate findings** for same `(target, family, candidate_path, signal_kind)`.

## Open follow-ups (post-implementation, tracked)

- WebGoat/DVWA fixture wiring (every spec recommends primary; MVP uses in-test mocks).
- Cross-run idempotence + `stale` flip — shared infra gap (1.16/1.17/1.19/WKP all defer).
- `_shared/soft_404.py` lift — only WKP needs it today; lift on 2nd consumer.
- Authenticated-context probes (specs 20/21/22 mention; Phase 2 auth-state-machine dependency).
- Per-family false-positive guards (docs-like page detection, SPA fall-through) — present in each spec; MVP focuses on soft-404 as the umbrella defense.

## Audit verdict

**Specs are internally consistent across the 6-family set.** Single-stub absorption is justified by uniform detection pattern + shared safety controls. Severity ceiling `medium` is uniform. Most-restrictive cross-spec resolution lands cleanly (HEAD-first + 65536 cap + same-origin one-hop). `Family` enum + per-family Signature/redactor strategies + soft-404 baseline are the right structural pieces. Proceeding to slice WKP-A.
