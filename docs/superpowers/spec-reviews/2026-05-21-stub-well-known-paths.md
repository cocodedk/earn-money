# Stub `well_known_paths` — post-implementation 6-spec audit

> Pre-impl audit: [`2026-05-21-stub-well-known-paths-pre.md`](2026-05-21-stub-well-known-paths-pre.md)
> Implementation: slices WKP-AUDIT → WKP-D on `feat/em-backend-well-known-paths`
> Audit date: 2026-05-20

## Family coverage

| Family | Spec | Detection | Redaction |
|--------|------|-----------|-----------|
| `env` | 1.20 | KEY=VALUE line regex + sensitive-key boost | KEY=<REDACTED>; generic secret sweep |
| `git` | 1.21 | `ref: refs/`, `[remote "..."]`, `PACK` magic | ASCII preserved; binary → `<magic:..>` |
| `config_files` | 1.22 | Spring datasource keys, Rails `database.yml`, `services:` root | Generic secret/PII sweep |
| `logs` | 1.23 | ISO-8601 + log level, nginx combined-log | Email/IP/JWT redaction |
| `backup_archives` | 1.24 | ZIP/gzip/7z/RAR magic | Magic prefix preserved, body redacted |
| `db_dumps` | 1.25 | `CREATE TABLE`, `INSERT INTO`, SQLite magic | SQL: keep CREATE; INSERT VALUES → `(<REDACTED>)` |

## Persistence contract

| Spec field | Implementation |
|------------|----------------|
| `Finding.category` = `well_known_paths.<family>` | ✅ `runner_findings.py:_CATEGORY_PREFIX` + verdict.family |
| `Finding.severity` per family hint, capped at MEDIUM | ✅ `families.py` (env/git/archives/db → MEDIUM; config/logs → LOW); `classify._severity_for` collapses low-confidence to INFO |
| `Finding.status` = `candidate` for new findings | ✅ `runner_findings.py:47` |
| `Finding.data.family`, `.candidate_path`, `.signature_id`, `.redacted_excerpt`, `.evidence_ids` | ✅ |
| `Evidence` per probe with family + candidate_path in data | ✅ `runner_evidence.py` |

## Cross-spec must-not assertions (consolidated)

| Spec must-not | Test / code guard |
|---------------|-------------------|
| No mutating HTTP methods | Only HEAD + GET in `fetcher.py`; runner never POSTs |
| No full-file downloads | `fetcher.py` always sends `Range: bytes=0-{max-1}`; archives/db_dumps capped at 4096 |
| No content extraction from archives | `redact.py` redacts archive body whole; magic prefix only persisted |
| No following of out-of-scope URLs | `_same_origin` check at both HEAD and GET — fail-closed |
| No hostname hard-coding | All detection via signatures; no host-keyed branches |
| No LLM / AI calls | Deterministic only |
| No retry after timeouts/TLS | `httpx.TransportError` → status=0, empty body |
| No persistence of cookies/auth/tokens | Redaction layer runs before persist |
| No fuzzing / brute-force | Spec-curated path lists only |
| No high/critical severity | `_severity_for` capped via family hints (max MEDIUM) |
| No duplicate findings | One Finding per (target, family, candidate, hit) — runner persists one per soft-404-clearing positive verdict |

## Cross-tier safety

- Single `@register("1.20")` — owns 1.20-1.25 absorption. Specs 1.21-1.25 closure-noted, NOT registered separately (asserted in `test_registration.py`).
- `FINDING_CREATED` enum value added to `apps/events/types.py` per plan (was previously missing).
- Body decoding uses `errors="replace"` — non-UTF-8 archives stay safe.

## Acceptance criteria

| Criterion | Met |
|-----------|-----|
| Uses shared ScanTarget + Evidence | ✅ |
| Defines only stub-specific types | ✅ (`Family`, `Signature`, `Verdict`, `FamilySpec`, `SoftFootprint`) |
| Deterministic, no LLM | ✅ |
| Read-only requests | ✅ HEAD + GET only |
| Caps requests | ✅ per-family path list bounded |
| Handles HTML/JSON/YAML/text/binary | ✅ matcher branches on magic-bytes vs text |
| Transport errors graceful | ✅ |
| Stores redacted snippets | ✅ via `redact.py` before `runner_findings.emit_finding` |
| Soft-404 defense | ✅ `soft_404.py` baseline + `matches_soft_404` |
| HEAD-first + Range fetcher | ✅ `fetcher.py` |
| Same-origin redirect policy | ✅ both HEAD + GET |
| Cross-run idempotence + stale flip | ❌ deferred (shared infra) |
| 100% line + branch coverage | ✅ on production code |

## Deferred follow-ups (tracked)

1. Cross-run idempotence + `stale` flip — shared infra gap (1.16/1.17/1.19/WKP all defer).
2. WebGoat/DVWA integration fixture wiring — every spec recommends; MVP uses in-test mocks.
3. Authenticated-context probes (specs 20/21/22 mention; Phase 2 auth dependency).
4. `_shared/secrets.py` lift — 1.17 + 1.19 + WKP all consume the same redaction patterns; cross-stub import works but should lift.
5. `_shared/soft_404.py` lift — only WKP uses it today; lift on 2nd consumer.
6. Per-family false-positive guards (docs-like page detection, SPA fall-through) — soft-404 is the umbrella; per-family refinements are follow-ups.
7. Per-target candidate-path overrides — runtime config, MVP uses curated defaults only.

## Audit verdict

**Stub `well_known_paths` ships per spec for the MVP scope across all six absorbed specs.** Seven tracked follow-ups; none are blockers. Detection coverage exists per family. Soft-404 + HEAD-first + Range + same-origin + per-family redaction wire together correctly. Spec frontmatter flipped: 1.20–1.25 → `status: done`. Ready for stack merge per [[feedback-merge-heuristic]].
