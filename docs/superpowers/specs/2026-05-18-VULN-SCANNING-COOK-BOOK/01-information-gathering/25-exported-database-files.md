---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 25
slug: exported-database-files
status: done        # pending | in-progress | blocked | done — absorbed into stub well_known_paths (registered under spec 1.20)
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.25 Exported database files

> Phase 1 — Information gathering · Category: Sensitive files

> **Closure (2026-05-20):** Absorbed by stub `well_known_paths` (registered owner: spec [1.20](./20-env.md)). The `db_dumps` family covers `/db.sql`, `/backup.sql`, `/dump.sql`, `.sqlite`, `.sqlite3`, `.db`, `.mdb`, and similar exported database files per this spec. SQL text dumps preserve `CREATE TABLE` verbatim and redact `INSERT INTO ... VALUES (...)` value-tuples to `(<REDACTED>)`; SQLite/binary db files use the magic-prefix + binary-redacted strategy.

<!--
GPT-5.5: Enrichment zone — paste-ready spec contract for LLM-assisted implementation.

Goal: enrich this spec so a coding agent can implement it safely and consistently.

PROTECTED — do not modify:
- YAML frontmatter (between `---` fences at top of file).
- Title heading, blockquote breadcrumb, and the `##` section headings.

EDITABLE — fill these:
- The body under each `##` section. Sub-headings (`###`), lists, code blocks, tables welcome.

OUTPUT FORMAT:
- Return raw markdown directly. Do NOT wrap the response in a ` ```markdown ` code fence.
- Inside the body, use exactly 3 backticks for code fences. No 4-backtick blocks.

CONTENT RULES:
- Use shared `ScanTarget` and `Evidence` from ../00-shared-schema.md. Do not redefine them.
- Define only stub-specific `<Name>Signature` and `<Name>Finding` types.
- Detection is deterministic. AI is `None` unless a deterministic gap is named under Safety.
- Pass/fail check has explicit assertions, including negative ones (what must NOT happen).
- Confidence: `low | medium | high`. Finding status: `candidate | confirmed | rejected | stale`.
- Never hard-code hostname → expected tech; detect from response evidence.
- Follow the Coding-agent rules in ../00-shared-schema.md.
-->

## Purpose

Detect publicly reachable exported database files such as SQL dumps, SQLite databases, and database backup exports. These files often contain user records, password hashes, API keys, internal schema names, and business data. A runner cares because a single exposed dump can turn a low-noise information-gathering issue into full data disclosure without authentication or exploitation.

## Inputs

The runner receives a shared `ScanTarget` from `../00-shared-schema.md`.

Stub-specific inputs:

* `target.url`: base URL to probe.
* Optional credentials from the shared authenticated scan context, if the runner supports authenticated passive checks.
* Optional path scope from the scan policy.
* Optional denylist from the scan policy.
* Optional custom candidate filenames.
* Optional maximum response bytes to read per candidate.
* Optional request timeout.
* Optional user agent.
* Optional redirect policy.

Recommended default knobs:

| Knob                  |            Default | Notes                                                   |
| --------------------- | -----------------: | ------------------------------------------------------- |
| `max_candidate_paths` |              `150` | Hard cap after normalization and deduplication.         |
| `max_probe_depth`     |                `2` | Root plus shallow common directories only.              |
| `max_read_bytes`      |             `8192` | Enough for file signatures without collecting the dump. |
| `timeout_ms`          |             `5000` | Per request.                                            |
| `follow_redirects`    | `same-origin-only` | Do not follow cross-origin redirects.                   |
| `allow_authenticated` |            `false` | Default is unauthenticated probing.                     |
| `ai`                  |             `None` | No AI needed.                                           |

Candidate path configuration must be deterministic and auditable. The runner must not infer expected database technology from hostname, brand, favicon, page title, or previous assumptions. Technology hints may only come from response evidence.

## Detection logic

Use deterministic HTTP probing only.

### Candidate generation

Build candidate paths from a small, fixed list plus optional user-supplied additions.

Common directories:

* `/`
* `/backup/`
* `/backups/`
* `/db/`
* `/database/`
* `/databases/`
* `/dump/`
* `/dumps/`
* `/export/`
* `/exports/`
* `/private/`
* `/tmp/`

Common filenames:

* `database.sql`
* `db.sql`
* `dump.sql`
* `backup.sql`
* `site.sql`
* `app.sql`
* `data.sql`
* `prod.sql`
* `production.sql`
* `staging.sql`
* `dev.sql`
* `test.sql`
* `users.sql`
* `mysql.sql`
* `postgres.sql`
* `pg_dump.sql`
* `database.dump`
* `db.dump`
* `dump.dump`
* `backup.dump`
* `database.sqlite`
* `database.sqlite3`
* `db.sqlite`
* `db.sqlite3`
* `app.sqlite`
* `app.sqlite3`
* `data.sqlite`
* `data.sqlite3`
* `database.db`
* `db.db`
* `app.db`
* `data.db`

Compressed SQL export names may be included because many exposed dumps are stored as direct export files:

* `database.sql.gz`
* `db.sql.gz`
* `dump.sql.gz`
* `backup.sql.gz`
* `database.sql.zip`
* `db.sql.zip`
* `dump.sql.zip`
* `backup.sql.zip`

Do not recursively crawl directories for database exports in this stub. Use content discovery stubs for broad crawling.

### Request method discipline

For each candidate URL:

1. Send `HEAD` when the runner supports it.
2. If `HEAD` returns `200`, `206`, `403`, `405`, or a weakly useful response, send a bounded `GET`.
3. Use `Range: bytes=0-8191` for the bounded `GET`.
4. If the server ignores the range request, stop reading after `max_read_bytes`.
5. Do not request the full file.
6. Do not decompress compressed responses unless the shared safe decompression helper supports hard byte, ratio, and time limits.
7. Do not send POST, PUT, PATCH, DELETE, or OPTIONS for this stub.

`403` can be recorded as a candidate only when the URL path strongly indicates an exported database file. It must not be confirmed without readable database evidence.

### Positive evidence

A finding can be `confirmed` when all of these are true:

* HTTP status is `200` or `206`.
* The response is not a generic HTML error page, login page, SPA shell, or soft 404.
* The path, headers, or body indicate an exported database file.
* At least one strong database signature is present in the bounded evidence.

Strong database signatures include:

| Database/export type  | Deterministic signal                                                                                                                                      |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SQLite                | Body starts with `SQLite format 3\0`.                                                                                                                     |
| MySQL dump            | Body contains `-- MySQL dump`, `CREATE TABLE`, `LOCK TABLES`, or `INSERT INTO` in dump-like context.                                                      |
| PostgreSQL dump       | Body contains `-- PostgreSQL database dump`, `COPY ... FROM stdin;`, `SET statement_timeout`, or `pg_dump` markers.                                       |
| Generic SQL export    | Body contains schema/data dump patterns such as `CREATE TABLE`, `DROP TABLE`, `INSERT INTO`, `ALTER TABLE`, `CREATE INDEX`, with SQL-like line structure. |
| Compressed SQL export | Filename strongly indicates SQL export and archive header is present, such as gzip or zip magic, without full extraction.                                 |
| Access/Jet database   | Body contains the known Jet database marker `Standard Jet DB` in the initial bytes.                                                                       |

Weak signals may produce `candidate` findings, not confirmed findings:

* File extension only, such as `.sql`, `.sqlite`, `.db`, `.dump`.
* `Content-Disposition` filename suggesting a database export.
* `Content-Type: application/octet-stream` with a database-like filename.
* `403` on a database-like candidate path.
* Very small first chunk with only partial SQL syntax.

### Negative evidence

Reject or ignore responses that match any of these:

* HTTP `404`, `410`, or `451`.
* HTTP `401` unless authenticated scanning is explicitly enabled.
* HTTP `3xx` to a different origin.
* HTML document with normal application shell content.
* Login page, marketing page, documentation page, or API JSON error.
* Soft 404 detected by shared response similarity logic.
* Directory listing without a directly readable database export.
* File extension match where body clearly is not a database export.
* JavaScript bundle, source map, image, PDF, CSS, or normal API response.
* WAF/block page unless the URL itself strongly indicates an exported database file; in that case store a low-confidence `candidate`.

### Confidence rules

Use deterministic evidence only:

* `high`: readable `200` or `206` response with strong database signature.
* `medium`: readable response with database-like filename plus multiple SQL dump markers.
* `low`: extension-only match, blocked response on a database-like path, or partial signature.
* `rejected`: checked candidate was not a database export.
* `stale`: previously confirmed evidence is no longer reachable or now returns unrelated content.

### Evidence handling

For each positive or candidate result, store bounded evidence:

* URL
* status code
* method
* redirect chain
* selected headers
* first `max_read_bytes` only
* content length, if provided
* content type
* content disposition, if provided
* content hash of captured bytes
* matched signatures
* truncation flag

Do not store full database exports in normal finding records. If the project has a secure evidence vault, this stub still stores only the bounded first chunk unless a user-approved workflow requests more.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only stub-specific types:

```ts
export type ExportedDatabaseFileSignature = {
  id: string;
  name: string;
  kind:
    | "sqlite_magic"
    | "mysql_dump_marker"
    | "postgres_dump_marker"
    | "generic_sql_dump_marker"
    | "compressed_sql_export_name"
    | "compressed_file_magic"
    | "jet_db_marker"
    | "content_disposition_filename"
    | "extension_hint"
    | "blocked_database_like_path";
  matched: boolean;
  match_excerpt?: string;
  byte_offset?: number;
  confidence: "low" | "medium" | "high";
};

export type ExportedDatabaseFileFinding = {
  id: string;
  target_id: ScanTarget["id"];
  url: string;
  method: "HEAD" | "GET";
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  evidence_ids: Evidence["id"][];
  signatures: ExportedDatabaseFileSignature[];
  http_status: number;
  content_type?: string;
  content_length?: number;
  content_disposition?: string;
  detected_export_type:
    | "sqlite"
    | "mysql_dump"
    | "postgres_dump"
    | "generic_sql_dump"
    | "compressed_sql_export"
    | "jet_db"
    | "unknown_database_export";
  bytes_sampled: number;
  response_truncated: boolean;
  redirect_chain: string[];
  reason: string;
  remediation: string;
  created_at: string;
  updated_at: string;
};
```

Persistence rules:

* Store one finding per canonical URL.
* Update existing findings by canonical URL and target ID.
* Preserve old evidence IDs when a finding moves to `stale`.
* Mark a finding `stale` when a previously confirmed URL no longer returns matching evidence.
* Mark a finding `rejected` only for deterministic negative checks that were explicitly executed.
* Do not persist raw full dumps, secrets extracted from dumps, or unbounded bodies.
* Use the shared evidence redaction and hashing rules before persistence.

## Safety

This stub is read-only.

Allowed methods:

* `HEAD`
* `GET`

Blocked methods:

* `POST`
* `PUT`
* `PATCH`
* `DELETE`
* Any method that mutates state.
* Any method that submits forms or triggers export generation.

Payload restrictions:

* No request body.
* No SQL payloads.
* No fuzzing payloads.
* No authentication attempts.
* No brute force.
* No directory traversal payloads.
* No parameter mutation.
* No attempt to create, trigger, or regenerate database exports.

Response restrictions:

* Use bounded reads.
* Prefer `Range` requests.
* Stop reading after `max_read_bytes`.
* Do not download complete database files.
* Do not print database contents to logs.
* Do not extract rows, users, password hashes, access tokens, or business data.
* Do not decompress archives unless a shared safe decompression helper enforces strict byte, time, and ratio limits.

PII handling:

* Treat all matched database evidence as sensitive.
* Store only short, redacted excerpts needed to explain the signature.
* Redact emails, tokens, password hashes, session IDs, API keys, and obvious secrets in excerpts.
* Store content hashes instead of content where possible.
* Never include sampled database rows in normal reports.

AI involvement: `None`.

No deterministic gap needs AI. The scanner can classify exported database files from paths, headers, magic bytes, and SQL dump markers. If a future implementation asks an LLM to explain remediation, it must use validated finding metadata only, not raw database content.

## Pass/fail check

The implementation passes when these assertions hold.

### Positive assertions

* Given `/database.sql` returning `200` with `-- MySQL dump`, the runner creates one `confirmed` finding with `confidence: "high"`.
* Given `/db.sqlite` returning `200` with `SQLite format 3\0`, the runner creates one `confirmed` finding with `confidence: "high"`.
* Given `/backup.sql.gz` returning gzip magic bytes and a database-export filename, the runner creates at least a `candidate` finding.
* Given `/dump.sql` returning `206` with SQL dump markers, the runner creates a `confirmed` finding.
* Given `Content-Disposition: attachment; filename="database.sql"` and SQL dump markers, the runner records the matching signature.
* The finding references shared `Evidence` IDs.
* The finding stores `bytes_sampled`.
* The finding records whether the response was truncated.
* The finding records matched signatures.
* The runner deduplicates the same canonical URL.
* A previously confirmed URL that later returns `404` becomes `stale`.

### Negative assertions

* The runner must not download a complete database export.
* The runner must not read beyond `max_read_bytes`.
* The runner must not log raw database rows.
* The runner must not extract or store passwords, hashes, tokens, or user records as finding fields.
* The runner must not send POST, PUT, PATCH, DELETE, or form submissions.
* The runner must not trigger application export endpoints.
* The runner must not infer MySQL, PostgreSQL, SQLite, or any database type from hostname.
* The runner must not confirm a finding from extension alone.
* The runner must not confirm a normal HTML page served at `/database.sql`.
* The runner must not confirm a soft 404 page.
* The runner must not follow cross-origin redirects.
* The runner must not decompress compressed files without bounded safe decompression.
* The runner must not use AI for detection.
* The runner must not create duplicate findings for the same canonical URL.

## Test fixtures

Use a new fixture: `exported-database-files`.

The fixture should expose deterministic static files in a local container. Do not include real user data or real secrets.

Suggested routes:

| Route                     | Behavior                                                                                                | Expected result                                            |
| ------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `/database.sql`           | `200`, text body starts with `-- MySQL dump` and contains toy `CREATE TABLE` / `INSERT INTO` statements | `confirmed`, `high`                                        |
| `/db.sqlite`              | `200`, body starts with `SQLite format 3\0` and small dummy bytes                                       | `confirmed`, `high`                                        |
| `/pg_dump.sql`            | `200`, body contains `-- PostgreSQL database dump` and `COPY public.example FROM stdin;`                | `confirmed`, `high`                                        |
| `/backup.sql.gz`          | `200`, gzip magic bytes, no decompression required                                                      | `candidate`, `low` or `medium`                             |
| `/forbidden/database.sql` | `403`, no body                                                                                          | `candidate`, `low`                                         |
| `/fake/database.sql`      | `200`, HTML application shell                                                                           | `rejected`                                                 |
| `/missing/database.sql`   | `404`                                                                                                   | no finding or `rejected`, depending on shared runner style |
| `/soft404/db.sql`         | `200`, standard not-found HTML                                                                          | `rejected`                                                 |
| `/redirect/db.sql`        | `302` to another origin                                                                                 | `rejected`                                                 |

Fixture data rules:

* Use toy table names such as `example_users`.
* Use fake values such as `alice@example.test`.
* Do not include real passwords, hashes, tokens, or production-looking credentials.
* Keep every file small.
* Include headers needed for testing `Content-Type`, `Content-Length`, `Content-Disposition`, range support, and ignored range behavior.

If an existing fixture framework requires using `juice-shop`, `dvwa`, or `webgoat`, add this as a synthetic sidecar fixture rather than depending on vulnerable-app internals. This check is about exposed static files, not an application-specific bug.

## Acceptance criteria

Operational quality bar:

* Idempotent: repeated runs produce the same finding IDs for the same canonical URL and evidence.
* Deterministic: detection uses only HTTP response evidence, path evidence, headers, and byte signatures.
* Bounded: never reads more than configured `max_read_bytes` per candidate.
* Safe by default: unauthenticated, read-only, no export-triggering behavior.
* Fast: completes within the shared phase budget with `max_candidate_paths` enforced.
* Scope-aware: respects target scope, denylist, redirect policy, and authenticated-scan settings.
* TLS-aware: handles certificate errors according to shared runner policy and records a clean scan error instead of crashing.
* Redirect-safe: follows same-origin redirects only when configured.
* Retry-safe: no flaky retry loops; at most one retry for transient network errors if shared policy allows it.
* Evidence-safe: stores bounded, redacted evidence only.
* Logging-safe: no raw dump content, secrets, cookies, credentials, or sampled rows in logs.
* Compatible: uses shared `ScanTarget`, shared `Evidence`, shared HTTP client, shared canonical URL logic, shared redaction, and shared error types.
* Testable: unit tests cover candidate generation, signatures, confirmation, rejection, stale transition, byte caps, redirect handling, and no-mutating-method guarantees.

