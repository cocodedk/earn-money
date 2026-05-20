---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 24
slug: backup-archives
status: done        # pending | in-progress | blocked | done — absorbed into stub well_known_paths (registered under spec 1.20)
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.24 Backup archives

> Phase 1 — Information gathering · Category: Sensitive files

> **Closure (2026-05-20):** Absorbed by stub `well_known_paths` (registered owner: spec [1.20](./20-env.md)). The `backup_archives` family handles `.zip`, `.tar.gz`, `.tgz`, `.7z`, `.rar`, and other archive paths per this spec. Magic-byte prefix read only (4096-byte Range cap) — no full-file downloads. Content body is redacted entirely (`<binary-redacted bytes=N>`).

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

Detect publicly reachable backup archive files such as `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.7z`, and `.rar` that may expose source code, uploaded files, database dumps, configuration, or credentials. A runner cares because these files are often created during deployment or migration and left in the web root, where a simple unauthenticated request can disclose large parts of an application.

## Inputs

The runner receives a shared `ScanTarget` from `../00-shared-schema.md`.

Required input:

* `ScanTarget.url`: Base URL or scoped URL to test.
* Shared scan scope rules from `ScanTarget`, including allowed hosts, ports, schemes, and path boundaries.

Optional configuration knobs:

| Name                           | Type         |   Default | Notes                                                                                    |
| ------------------------------ | ------------ | --------: | ---------------------------------------------------------------------------------------- |
| `max_candidate_paths`          | integer      |      `80` | Hard cap after path generation and de-duplication.                                       |
| `request_timeout_ms`           | integer      |    `8000` | Per request timeout.                                                                     |
| `max_redirects`                | integer      |       `2` | Follow only same-scope redirects.                                                        |
| `use_head_first`               | boolean      |    `true` | Try `HEAD` before ranged `GET`.                                                          |
| `allow_range_probe`            | boolean      |    `true` | Allows `GET` with `Range: bytes=0-511` when `HEAD` is missing, blocked, or inconclusive. |
| `max_probe_bytes`              | integer      |     `512` | Maximum bytes to read from a candidate archive response.                                 |
| `candidate_extensions`         | list[string] | see below | Archive extensions to test.                                                              |
| `candidate_names`              | list[string] | see below | Filename stems to test.                                                                  |
| `include_target_derived_names` | boolean      |    `true` | Adds names derived from response evidence and URL path segments.                         |
| `treat_html_200_as_negative`   | boolean      |    `true` | Prevents false positives from SPA fallback pages and branded 404s.                       |

Default archive extensions:

```text
.zip
.tar
.tar.gz
.tgz
.tar.bz2
.tbz2
.tar.xz
.txz
.7z
.rar
.gz
.bz2
.xz
```

Default candidate name stems:

```text
backup
backups
archive
archives
site
website
web
www
public
public_html
html
htdocs
app
application
source
src
code
release
deploy
deployment
prod
production
staging
dev
development
dump
db
database
sql
mysql
postgres
pgsql
files
uploads
media
```

Target-derived candidate names may be built from deterministic evidence only:

* URL host labels, after normalizing to lowercase and removing unsafe characters.
* URL path segments in scope.
* Observed title/application name from an already fetched same-origin HTML page.
* Observed technology names from headers or body evidence, such as framework headers, generator tags, or static asset paths.

Do not infer technology from the hostname alone. For example, do not assume a target uses WordPress because the domain contains `wp`; only use WordPress-specific stems if the scanner saw WordPress evidence such as `/wp-content/`, `wp-json`, or a WordPress generator tag.

## Detection logic

Detection is deterministic and read-only.

### 1. Normalize scope

1. Parse `ScanTarget.url`.
2. Normalize scheme, host, port, and base path according to shared scanner rules.
3. Reject candidates outside the target scope before sending any request.
4. De-duplicate paths after URL normalization.

### 2. Build candidate paths

Generate candidate paths by combining candidate stems and archive extensions.

Always include root-level candidates:

```text
/{stem}{extension}
```

If the target URL has an in-scope path, include path-local candidates:

```text
/{base_path}/{stem}{extension}
```

If target-derived names are enabled, add safe stems from deterministic evidence:

```text
/{target_name}{extension}
/{target_name}-backup{extension}
/{target_name}_backup{extension}
/backup-{target_name}{extension}
/backup_{target_name}{extension}
```

Also test common backup directories with the same filename patterns, capped by `max_candidate_paths`:

```text
/backup/{stem}{extension}
/backups/{stem}{extension}
/archive/{stem}{extension}
/archives/{stem}{extension}
/old/{stem}{extension}
/tmp/{stem}{extension}
/_private/{stem}{extension}
```

Candidate generation must be stable. Given the same target, config, and evidence, the runner must produce the same candidate list in the same order.

### 3. Probe each candidate

Preferred request order:

1. `HEAD` candidate URL.
2. If `HEAD` is unsupported, blocked, returns `405`, or lacks enough evidence, send `GET` with:

```text
Range: bytes=0-511
Accept: */*
```

Do not send a full-body archive download request.

A candidate response is considered worth evaluating when status is one of:

* `200 OK`
* `206 Partial Content`
* `301`, `302`, `303`, `307`, `308` to a same-scope URL
* `401 Unauthorized`
* `403 Forbidden`

Redirect handling:

* Follow at most `max_redirects`.
* Follow only same-scope redirects.
* If a redirect leaves scope, store evidence for the redirect and mark the candidate `rejected`.
* If a redirect lands on a generic HTML page, mark the candidate `rejected`.

### 4. Confirm archive signatures

Use status, headers, and the first bytes of the body.

Archive magic-byte signatures:

| Format | Extension examples          | Magic bytes / deterministic signal                           |
| ------ | --------------------------- | ------------------------------------------------------------ |
| ZIP    | `.zip`                      | `50 4B 03 04`, `50 4B 05 06`, or `50 4B 07 08`               |
| gzip   | `.gz`, `.tar.gz`, `.tgz`    | `1F 8B`                                                      |
| bzip2  | `.bz2`, `.tar.bz2`, `.tbz2` | `42 5A 68`                                                   |
| xz     | `.xz`, `.tar.xz`, `.txz`    | `FD 37 7A 58 5A 00`                                          |
| 7z     | `.7z`                       | `37 7A BC AF 27 1C`                                          |
| rar    | `.rar`                      | `52 61 72 21 1A 07 00` or `52 61 72 21 1A 07 01 00`          |
| tar    | `.tar`                      | `ustar` at byte offset `257` when enough bytes are available |

Header signals that support detection but do not confirm it alone:

* `Content-Type: application/zip`
* `Content-Type: application/x-zip-compressed`
* `Content-Type: application/gzip`
* `Content-Type: application/x-gzip`
* `Content-Type: application/x-tar`
* `Content-Type: application/x-7z-compressed`
* `Content-Type: application/vnd.rar`
* `Content-Disposition` filename ending in an archive extension
* `Accept-Ranges: bytes`
* Large `Content-Length` with an archive extension path

### 5. Reject common false positives

Reject a candidate when any of these are true:

* Response status is `404`, `410`, or another clear miss.
* Response is `200` but body is HTML and no archive magic bytes are present.
* Response is a SPA fallback page.
* Response is a branded 404 or soft 404.
* Response content type is `text/html`, `application/xhtml+xml`, `text/plain`, or JSON without archive magic bytes.
* Response body contains an obvious application page rather than archive bytes.
* URL extension is archive-like but final redirected path is not archive-like and no archive signature is present.
* Body is shorter than the magic-byte check requires and headers do not support an archive claim.
* Response is a directory listing page, not the archive itself. Directory listing is a separate finding type.

Soft-404 detection should use deterministic checks already present in the scanner, if available. If not available, this stub may use simple local checks:

* HTML title or heading contains `404`, `not found`, `page not found`, or equivalent common English strings.
* Body contains the requested path inside a not-found message.
* Response size and hash match a known baseline 404 response fetched for a random in-scope path during the same scan.

### 6. Confidence and status

Use these rules:

| Status      | Confidence | Conditions                                                                                                                             |
| ----------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `confirmed` | `high`     | `200` or `206` and archive magic bytes match.                                                                                          |
| `candidate` | `medium`   | `200` or `206`, archive-like path, archive content type or disposition, but magic bytes unavailable because only `HEAD` was usable.    |
| `candidate` | `medium`   | `401` or `403` on archive-like path with archive content type or disposition.                                                          |
| `candidate` | `low`      | `401` or `403` on archive-like path without archive headers.                                                                           |
| `rejected`  | `high`     | Clear miss, soft 404, HTML fallback, out-of-scope redirect, or non-archive content.                                                    |
| `stale`     | `low`      | A previously confirmed archive is no longer reachable in the current scan. Only use when comparing against stored historical findings. |

Do not mark a finding `confirmed` from filename alone.

### 7. Evidence collection

Store one `Evidence` item per probe attempt that supports the decision.

Evidence should include:

* Request method.
* Candidate URL.
* Final URL after redirect.
* Status code.
* Response headers relevant to archive detection.
* Content type.
* Content length.
* Range support.
* First bytes hash.
* Magic-byte match result.
* Redirect chain, if any.
* Soft-404 comparison result, if used.
* Timestamp.
* Truncation flag.

Do not store archive contents. Store only a short byte prefix, preferably encoded as hex, when the shared evidence model permits it. If the shared schema has a safer binary-snippet field, use that instead.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine either type.

Define only these stub-specific types.

```ts
export type BackupArchiveFormat =
  | "zip"
  | "tar"
  | "gzip"
  | "bzip2"
  | "xz"
  | "7z"
  | "rar"
  | "unknown";

export type BackupArchiveSignature = {
  id: string;
  candidate_url: string;
  final_url: string;
  method: "HEAD" | "GET";
  status_code: number;
  archive_format: BackupArchiveFormat;
  extension: string;
  content_type?: string;
  content_length?: number;
  content_disposition_filename?: string;
  accept_ranges?: boolean;
  magic_bytes_checked: boolean;
  magic_bytes_matched: boolean;
  magic_bytes_name?: string;
  body_prefix_sha256?: string;
  body_prefix_size?: number;
  range_request_used: boolean;
  redirect_chain: string[];
  soft_404_checked: boolean;
  soft_404_matched: boolean;
  evidence_ids: string[];
};

export type BackupArchiveFinding = {
  id: string;
  target_id: string;
  url: string;
  final_url: string;
  title: string;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  archive_format: BackupArchiveFormat;
  signature: BackupArchiveSignature;
  evidence_ids: string[];
  first_seen_at: string;
  last_seen_at: string;
  risk_summary: string;
  remediation: string;
};
```

Persistence rules:

* `BackupArchiveFinding.evidence_ids` must reference shared `Evidence` records.
* `BackupArchiveFinding.signature.evidence_ids` must be a non-empty subset of the finding evidence IDs.
* Do not persist archive body contents.
* Do not persist extracted filenames from inside the archive because the scanner must not download or extract archives in this stub.
* Use a stable finding fingerprint based on target ID, normalized final URL, archive format, and signature class.
* If the same URL is seen again with changed headers or content hash, update `last_seen_at` and append new evidence.
* If a previously confirmed finding is not present in a later scan, mark it `stale` only when the scanner has enough evidence that the same candidate URL was retested.

## Safety

This check is read-only.

Allowed HTTP behavior:

* `HEAD` requests to in-scope candidate URLs.
* `GET` requests only with `Range: bytes=0-511`, unless the shared runner has a stricter range limit.
* Same-scope redirects up to `max_redirects`.

Disallowed behavior:

* Full archive download.
* Archive extraction.
* Password guessing.
* Directory brute force beyond the configured candidate cap.
* Requests outside `ScanTarget` scope.
* Authenticated requests unless the shared runner explicitly provides scoped credentials for this target.
* Mutation methods such as `POST`, `PUT`, `PATCH`, and `DELETE`.
* Writing discovered URLs to third-party services.
* Sending archive contents to AI or external analysis services.

PII and secret handling:

* Treat any reachable archive as potentially sensitive.
* Store headers and a minimal byte prefix hash only.
* Do not store full archive bytes.
* Do not try to list files inside the archive.
* Do not attempt to identify secrets inside the archive in this stub.
* Redact cookies, authorization headers, and configured secret patterns from evidence.

AI involvement: `None`.

The scanner rule remains that hostile target content is untrusted evidence and must not control tools, scope, severity, persistence, or reporting. This follows the project’s LLM safety direction: the model may read evidence and propose analysis, while application code owns validation and actions. 

Deterministic gap:

* If a response is `403` or `401`, the runner cannot prove the body is an archive unless headers provide enough evidence.
* If `HEAD` is allowed but ranged `GET` is blocked, confidence must remain `medium` or lower unless a strong archive header is present.
* Do not use AI to guess whether a protected candidate is a real archive.

## Pass/fail check

A coding agent implementation passes when all assertions below are true.

Positive assertions:

* Given a target serving `/backup.zip` with ZIP magic bytes, the scanner creates one `BackupArchiveFinding` with:

  * `status = "confirmed"`
  * `confidence = "high"`
  * `archive_format = "zip"`
  * at least one linked `Evidence` record
* Given a target serving `/site.tar.gz` with gzip magic bytes, the scanner confirms it as `gzip`.
* Given a target serving `/archive.7z` with 7z magic bytes, the scanner confirms it as `7z`.
* Given a target where `HEAD /backup.zip` returns `405`, the scanner falls back to ranged `GET` when `allow_range_probe = true`.
* Given a target where ranged `GET /backup.zip` returns `206` and matching magic bytes, the scanner confirms the finding.
* Given a target where `/backup.zip` returns `403` with `Content-Type: application/zip`, the scanner creates a `candidate` finding with `medium` confidence.
* Given a target where `/backup.zip` returns `403` without archive headers, the scanner creates at most a `candidate` finding with `low` confidence.
* Given a same-scope redirect from `/backup.zip` to `/files/backup.zip` with archive magic bytes, the scanner records the redirect chain and confirms the final URL.
* Given a previous confirmed finding that is retested and now returns a clear `404`, the scanner may mark the old finding as `stale`.

Negative assertions:

* The scanner must not mark a finding `confirmed` from filename alone.
* The scanner must not mark HTML fallback pages as backup archives.
* The scanner must not mark branded 404 pages as backup archives.
* The scanner must not follow out-of-scope redirects.
* The scanner must not send `POST`, `PUT`, `PATCH`, or `DELETE`.
* The scanner must not download the full archive.
* The scanner must not extract archive contents.
* The scanner must not store full archive bytes in evidence.
* The scanner must not send archive bytes to AI.
* The scanner must not exceed `max_candidate_paths`.
* The scanner must not hard-code hostname-to-technology assumptions.
* The scanner must not add WordPress, Django, Rails, Laravel, or other technology-specific archive names unless the technology was detected from response evidence.
* The scanner must not create duplicate findings for the same normalized final URL and archive format.
* The scanner must not retry indefinitely after timeout, TLS failure, or connection reset.
* The scanner must not treat a directory listing page as this finding type.

Example test cases:

```ts
expect(finding.status).toBe("confirmed");
expect(finding.confidence).toBe("high");
expect(finding.archive_format).toBe("zip");
expect(finding.evidence_ids.length).toBeGreaterThan(0);

expect(requests.every((r) => ["HEAD", "GET"].includes(r.method))).toBe(true);
expect(requests.some((r) => r.method === "POST")).toBe(false);
expect(requests.some((r) => r.headers["Range"] === "bytes=0-511")).toBe(true);

expect(evidence.body_full).toBeUndefined();
expect(signature.magic_bytes_matched).toBe(true);
expect(signature.soft_404_matched).toBe(false);
```

## Test fixtures

Preferred fixture: `juice-shop`.

Add a small fixture route or static file in the scanner test harness, not in the upstream application, if Juice Shop does not expose a stable public backup archive by default.

Fixture slug: `backup-archives`.

Fixture behavior:

| Path                  | Response                                                | Expected result             |
| --------------------- | ------------------------------------------------------- | --------------------------- |
| `/backup.zip`         | `200`, ZIP magic bytes, `Content-Type: application/zip` | `confirmed`, `high`, `zip`  |
| `/site.tar.gz`        | `206`, gzip magic bytes after ranged GET                | `confirmed`, `high`, `gzip` |
| `/archive.7z`         | `200`, 7z magic bytes                                   | `confirmed`, `high`, `7z`   |
| `/private-backup.zip` | `403`, `Content-Type: application/zip`                  | `candidate`, `medium`       |
| `/old-backup.zip`     | `200`, HTML branded 404 body                            | `rejected`, `high`          |
| `/backup.rar`         | Redirects to out-of-scope URL                           | `rejected`, `high`          |
| `/uploads.zip`        | `200`, normal HTML page                                 | `rejected`, `high`          |

Fixture implementation notes:

* Keep fixture archive bodies tiny.
* Use fixed byte strings with valid magic bytes; full valid archives are not required unless existing test helpers require them.
* Do not include real credentials, source code, database dumps, or personal data in fixtures.
* Include a baseline random missing path response so soft-404 checks can be tested.
* Include a `HEAD`-returns-`405` case to test ranged `GET` fallback.

Example tiny ZIP-like fixture body:

```text
PK\x03\x04fixture-backup-archive
```

Example tiny `GET` fallback.

Example tiny gzip-like fixture body:

```text
\x1f\x8bfixture-backup-archive
```

## Acceptance criteria

Operational quality bar:

* The check is idempotent. Running it twice against the same fixture creates no duplicate findings.
* The candidate list is deterministic and capped.
* The scanner completes within the phase budget for a normal target.
* Each request uses the shared timeout and cancellation mechanism.
* TLS errors, DNS errors, connection resets, timeouts, and malformed responses are handled gracefully and recorded as scan errors or rejected candidates, not crashes.
* Redirect handling respects scope.
* Ranged `GET` is used only when needed and only within the configured byte cap.
* Full archive contents are never downloaded, extracted, logged, persisted, or sent to AI.
* Evidence is enough for audit: method, URL, status, relevant headers, redirect chain, magic-byte result, body-prefix hash, and timestamp.
* Findings use only `low`, `medium`, or `high` confidence.
* Findings use only `candidate`, `confirmed`, `rejected`, or `stale` status.
* The implementation reuses shared `ScanTarget` and `Evidence`.
* Stub-specific persistence is limited to `BackupArchiveSignature` and `BackupArchiveFinding`.
* Tests cover confirmed archives, protected candidates, soft 404s, HTML fallbacks, redirects, timeout handling, duplicate prevention, request method discipline, and evidence minimization.

