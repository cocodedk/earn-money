---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 7
slug: backup-files
status: done        # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.7 Backup files

> Phase 1 — Information gathering · Category: Content discovery

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

Detect publicly reachable backup, temporary, editor, archive, database dump, and copied source files that were left under the web root. A runner cares because these files can expose source code, secrets, database contents, old endpoints, credentials, or deployment details without exploiting the application.

## Inputs

The runner receives:

* `ScanTarget` from `../00-shared-schema.md`.
* Seed URLs discovered by earlier content discovery, crawling, framework detection, route discovery, or server header checks.
* Optional credentials only if the current RoE profile allows authenticated read-only testing.
* Optional `robots.txt` and sitemap URLs if already collected by other specs.
* Config knobs:

  * `backup_files.enabled`, default `true`.
  * `backup_files.max_candidates_per_target`, default `300`.
  * `backup_files.max_candidates_per_seed`, default `12`.
  * `backup_files.max_direct_directory_names`, default `25`.
  * `backup_files.request_timeout_ms`, default `8000`.
  * `backup_files.max_redirects`, default `2`.
  * `backup_files.max_response_bytes`, default `65536`.
  * `backup_files.max_evidence_body_bytes`, default `8192`.
  * `backup_files.user_agent`, from shared scanner config.
  * `backup_files.allow_authenticated_requests`, inherited from RoE.
  * `backup_files.follow_same_origin_redirects_only`, default `true`.
  * `backup_files.include_directory_backup_names`, default `true`.
  * `backup_files.include_editor_swap_names`, default `true`.
  * `backup_files.include_archive_names`, default `true`.
  * `backup_files.soft_404_check`, default `true`.

The runner must work without credentials. Credentials only widen the readable evidence surface when the shared RoE allows it.

## Detection logic

Detection is deterministic and bounded.

### 1. Collect seed paths

Use only in-scope URLs from the target and earlier scan stages.

Seed sources may include:

* Target root path `/`.
* URLs discovered in HTML anchors, script tags, link tags, forms, redirects, and sitemaps.
* Paths found by hidden-route discovery.
* Static asset paths found by frontend framework or package leak checks.
* API paths found by earlier passive or bounded discovery.
* Existing confirmed application paths from the same scan.

Normalize each seed:

* Keep only same-origin URLs for the current `ScanTarget`.
* Remove fragments.
* Preserve query string only for evidence on the original seed, not for backup candidates.
* Collapse duplicate slashes in paths, except the URL scheme separator.
* Percent-decode only safe path characters.
* Drop paths with obvious binary media extensions unless config allows them:

  * `.png`
  * `.jpg`
  * `.jpeg`
  * `.gif`
  * `.webp`
  * `.ico`
  * `.woff`
  * `.woff2`
  * `.ttf`
  * `.mp4`
  * `.webm`
  * `.pdf`

Do not invent hostnames. Do not assume a known fixture by hostname.

### 2. Generate candidate backup paths

Generate candidates from observed paths and a small fixed set of backup naming rules.

For a seed file path such as `/admin/login.php`, generate:

* `/admin/login.php.bak`
* `/admin/login.php.backup`
* `/admin/login.php.old`
* `/admin/login.php.orig`
* `/admin/login.php.save`
* `/admin/login.php.copy`
* `/admin/login.php.tmp`
* `/admin/login.php.txt`
* `/admin/login.php~`
* `/admin/login.bak`
* `/admin/login.old`
* `/admin/.login.php.swp`
* `/admin/.login.php.swo`

For a seed file path without an extension such as `/config`, generate:

* `/config.bak`
* `/config.backup`
* `/config.old`
* `/config.orig`
* `/config.save`
* `/config.tmp`
* `/config.txt`
* `/config~`
* `/.config.swp`
* `/.config.swo`

For a seed directory such as `/admin/`, generate a capped list:

* `/admin/backup.zip`
* `/admin/backup.tar`
* `/admin/backup.tar.gz`
* `/admin/site.zip`
* `/admin/www.zip`
* `/admin/source.zip`
* `/admin/db.sql`
* `/admin/dump.sql`
* `/admin/database.sql`
* `/admin/backup.sql`
* `/admin/.env.bak`
* `/admin/config.php.bak`
* `/admin/settings.py.bak`

For root `/`, generate the same directory-level names at root, subject to the same cap.

If a path component has a safe slug, also generate archive names from that slug:

* `/<slug>.zip`
* `/<slug>.tar.gz`
* `/<slug>.sql`

Only use slug-derived archive names when the slug came from an observed in-scope path component. Do not run a broad wordlist.

Candidate generation must be stable. The same inputs and config must produce the same ordered candidate list.

### 3. Deduplicate and budget

Before probing:

* Deduplicate by normalized absolute URL.
* Keep stable order:

  1. File-derived candidates from high-confidence seed URLs.
  2. Directory-derived candidates.
  3. Root-level fallback candidates.
* Stop at `max_candidates_per_seed`.
* Stop at `max_candidates_per_target`.
* Record skipped candidate count in runner metrics.

### 4. Probe candidates

Use read-only HTTP only.

Preferred request sequence:

1. `HEAD` candidate URL.
2. If `HEAD` is unavailable, blocked, or does not provide enough evidence, use `GET`.
3. For `GET`, enforce response byte cap in the HTTP client. Do not rely only on `Content-Length`.
4. Send `Accept: */*`.
5. Send `Accept-Encoding: identity` where supported by the project HTTP client to make byte caps easier.
6. Use Range only if the existing HTTP client already supports it safely:

   * `Range: bytes=0-65535`

Allowed status handling:

* `200` or `206`: possible exposed backup file.
* `401` or `403`: possible protected backup path, but not confirmed exposure.
* `301`, `302`, `303`, `307`, `308`: follow only same-origin redirects, up to `max_redirects`.
* `404`, `410`: rejected.
* `429`, `500`, `502`, `503`, `504`: do not confirm. Mark probe error in metrics.
* Other statuses: rejected unless a future spec adds a deterministic rule.

A finding must not be confirmed from status alone.

### 5. Soft-404 rejection

When `soft_404_check=true`, compare candidate responses to a deterministic nonexistent path in the same directory.

Example baseline path:

```text
/<same-dir>/__scanner_missing_backup_file_<stable-target-hash>.bak
```

Reject the candidate when:

* Candidate and baseline have the same status and near-identical body hash.
* Candidate and baseline have very similar normalized text.
* Candidate returns the app shell HTML also returned by ordinary missing routes.
* Candidate content type is `text/html` and body title or main text matches the missing-page baseline.
* Candidate redirects to the same login, error, or fallback page as the baseline.

Do not create a confirmed backup-file finding for SPA fallback HTML.

### 6. Confirm backup-like evidence

A candidate can become `confirmed` only when all of these are true:

* Path name matches a configured backup, temp, editor, archive, database dump, or copied-source naming rule.
* Response is `200` or `206`.
* Response is not a soft 404.
* Body, headers, or magic bytes support that the response is a file-like artifact.

Strong deterministic indicators include:

* Archive magic:

  * ZIP: `PK\x03\x04`
  * gzip: `\x1f\x8b`
  * tar-like content with readable tar headers within the first capped bytes.
* Database dump markers:

  * `CREATE TABLE`
  * `INSERT INTO`
  * `DROP TABLE`
  * `-- MySQL dump`
  * `PostgreSQL database dump`
  * `SQLite format 3`
* Source/config markers:

  * `<?php`
  * `import `
  * `from `
  * `def `
  * `class `
  * `function `
  * `module.exports`
  * `DATABASE_URL=`
  * `SECRET_KEY=`
  * `DB_PASSWORD=`
  * `AWS_ACCESS_KEY_ID=`
  * `BEGIN RSA PRIVATE KEY`
* Editor/temp markers:

  * Vim swap filename pattern `.name.ext.swp`
  * Backup suffix `~`
  * Temporary-source path plus source-code-like body.
* Response headers:

  * `Content-Type: application/zip`
  * `Content-Type: application/gzip`
  * `Content-Type: application/x-tar`
  * `Content-Type: application/sql`
  * `Content-Disposition` with backup-like filename.
  * Non-HTML content type with backup-like path.

### 7. Confidence rules

Use deterministic confidence only.

`high` confidence:

* Backup-like path.
* `200` or `206`.
* Not soft 404.
* Strong artifact indicator exists:

  * archive magic,
  * SQL dump marker,
  * SQLite magic,
  * clear source/config marker,
  * or matching `Content-Disposition` filename.
* Evidence was collected from the final same-origin URL.

`medium` confidence:

* Backup-like path.
* `200` or `206`.
* Not soft 404.
* Response headers and body are file-like but not enough for high confidence.
* Example: `text/plain` with source-looking content but no sensitive marker.

`low` confidence:

* Backup-like path.
* `200` or `206`.
* Not soft 404.
* Artifact evidence is weak or truncated.
* Keep as `candidate`, not `confirmed`, unless the project’s shared rules allow low-confidence confirmed informational findings.

`rejected`:

* Missing, soft-404, off-scope redirect, app-shell fallback, blocked by RoE, probe error without evidence, or ordinary page content.

`stale`:

* A previously stored finding no longer reproduces in a later scan of the same `ScanTarget`.

### 8. Classification

Classify confirmed or candidate findings as one of:

* `source_backup`
* `config_backup`
* `database_dump`
* `archive_backup`
* `editor_swap`
* `temporary_copy`
* `log_or_text_backup`
* `unknown_backup_artifact`

Classification must come from path, headers, body sample, and magic bytes. Do not use hostname-specific assumptions.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`.

Do not redefine shared types here.

### `BackupFileSignature`

Represents one deterministic backup-file detection rule.

```json
{
  "id": "backup-file-suffix-bak-v1",
  "name": "Backup suffix .bak",
  "enabled": true,
  "candidate_kind": "file_suffix | editor_swap | directory_backup_name | slug_archive_name",
  "path_pattern": "{seed_path}.bak",
  "applies_to": "file | directory | root | any",
  "expected_artifact_kinds": ["source_backup", "config_backup", "database_dump", "archive_backup", "unknown_backup_artifact"],
  "confirming_indicators": ["backup_like_path", "http_200_or_206", "not_soft_404", "file_like_body_or_headers"],
  "default_confidence": "medium",
  "max_body_bytes": 8192,
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

Required fields:

* `id`
* `name`
* `enabled`
* `candidate_kind`
* `path_pattern`
* `applies_to`
* `expected_artifact_kinds`
* `confirming_indicators`
* `default_confidence`

### `BackupFileFinding`

Represents one candidate, confirmed, rejected, or stale backup-file result.

```json
{
  "id": "uuid",
  "target_id": "ScanTarget.id",
  "signature_id": "backup-file-suffix-bak-v1",
  "url": "https://example.test/admin/login.php.bak",
  "final_url": "https://example.test/admin/login.php.bak",
  "seed_url": "https://example.test/admin/login.php",
  "method": "GET",
  "status": "candidate | confirmed | rejected | stale",
  "confidence": "low | medium | high",
  "artifact_kind": "source_backup | config_backup | database_dump | archive_backup | editor_swap | temporary_copy | log_or_text_backup | unknown_backup_artifact",
  "http_status": 200,
  "content_type": "text/plain",
  "content_length": 1842,
  "sampled_bytes": 8192,
  "body_truncated": true,
  "soft_404_checked": true,
  "soft_404_rejected": false,
  "redirect_count": 0,
  "matched_path_rule": "{seed_path}.bak",
  "matched_indicators": ["backup_like_path", "source_marker", "secret_like_marker"],
  "sensitive_markers": ["SECRET_KEY"],
  "evidence_ids": ["Evidence.id"],
  "reason": "Backup-like path returned source-looking text and was not a soft 404.",
  "first_seen_at": "ISO-8601",
  "last_seen_at": "ISO-8601",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

Required fields:

* `id`
* `target_id`
* `signature_id`
* `url`
* `status`
* `confidence`
* `artifact_kind`
* `http_status`
* `matched_path_rule`
* `matched_indicators`
* `evidence_ids`
* `reason`
* `first_seen_at`
* `last_seen_at`

### Evidence storage

For each probed candidate that becomes `candidate`, `confirmed`, `rejected`, or `stale`, store evidence according to shared `Evidence`.

Evidence should include:

* Request method.
* Request URL.
* Final URL after same-origin redirects.
* Response status.
* Response headers.
* Capped body sample.
* Body hash of sampled bytes.
* Whether the body was truncated.
* Soft-404 baseline evidence ID when applicable.
* Matched deterministic indicators.
* Redaction status.

Do not store full large backup files in this spec. Store capped samples and hashes. If the project later needs full artifact retention, that belongs in a separate evidence-storage spec with encryption, access control, retention, and legal review.

## Safety

This check is read-only.

Allowed HTTP methods:

* `HEAD`
* `GET`

Forbidden behavior:

* No `POST`, `PUT`, `PATCH`, `DELETE`, or state-changing methods.
* No brute-force wordlists.
* No recursive archive extraction.
* No nested file discovery inside downloaded archives.
* No directory traversal payloads.
* No path mutation outside the same origin.
* No off-scope redirect following.
* No credential guessing.
* No bypass payloads.
* No query-parameter fuzzing.
* No attempt to download full large archives or database dumps.
* No execution of discovered code.
* No secrets validation against third-party services.
* No exfiltration tests.

Request discipline:

* Enforce per-target candidate cap.
* Enforce per-response byte cap.
* Enforce timeout.
* Stop reading once `max_response_bytes` is reached.
* Respect shared RoE pause, cancel, and scope checks.
* Use the shared HTTP client so audit logging, TLS handling, proxy settings, and scope checks stay consistent.

PII and secret handling:

* Treat backup file content as sensitive.
* Store only capped body samples.
* Redact obvious secrets in logs.
* Do not print raw backup content to console logs.
* Evidence storage may keep the capped sample if the shared evidence store allows it.
* Reports should show the URL, artifact type, and short redacted snippet only.
* Do not include full database rows in findings.

AI involvement:

* `None`.

There is no deterministic gap that needs AI in the MVP. File type, confidence, and status are decided from URL rules, status codes, headers, magic bytes, body markers, and soft-404 comparison.

## Pass/fail check

A run passes when all assertions below hold.

### Positive assertions

Given an in-scope target with a reachable source backup:

* Seed `/admin/login.php` exists.
* Candidate `/admin/login.php.bak` returns `200`.
* Response is not soft-404.
* Body contains source-like markers.
* The runner creates one `BackupFileFinding`.
* `status` is `confirmed`.
* `confidence` is `high` or `medium`.
* `artifact_kind` is `source_backup`.
* The finding references at least one `Evidence.id`.
* The evidence contains request URL, status, headers, capped body sample, and body hash.

Given an in-scope target with a reachable SQL dump:

* Candidate `/backup.sql` or `/dump.sql` returns `200`.
* Body contains deterministic SQL dump markers.
* The runner creates one `BackupFileFinding`.
* `status` is `confirmed`.
* `artifact_kind` is `database_dump`.
* `sensitive_markers` includes only marker names, not full dumped data.

Given an in-scope target with a reachable ZIP backup:

* Candidate `/backup.zip` returns `200` or `206`.
* Body starts with ZIP magic bytes.
* The runner creates one `BackupFileFinding`.
* `artifact_kind` is `archive_backup`.
* The runner does not extract the archive.

Given an in-scope target with an editor swap file:

* Candidate `/.index.php.swp` returns `200`.
* Path matches editor-swap rule.
* Response is not soft-404.
* The runner creates a finding with `artifact_kind` `editor_swap`.

### Negative assertions

The runner must not:

* Create a finding for `404` or `410` responses.
* Create a confirmed finding for a soft-404 page.
* Create a confirmed finding for a SPA fallback page.
* Create a confirmed finding from `403` alone.
* Create a confirmed finding from a backup-like URL when the body matches the missing-page baseline.
* Follow redirects to another host.
* Probe URLs outside the `ScanTarget` scope.
* Use mutating HTTP methods.
* Run an unbounded wordlist.
* Exceed `max_candidates_per_target`.
* Read more than `max_response_bytes` from any response.
* Store full large archive or database dump bodies in ordinary logs.
* Extract archives.
* Execute discovered files.
* Validate discovered secrets against external services.
* Hard-code fixture hostnames or expected technologies.
* Call an AI model for this check.

### Re-run assertions

On a second run against the same unchanged fixture:

* The runner produces the same normalized candidate order.
* Duplicate findings are not created.
* Existing findings update `last_seen_at`.
* Findings that no longer reproduce become `stale`, not silently deleted.

## Test fixtures

Use a dedicated fixture slug:

* `backup-files-lab`

The fixture should expose deterministic routes under a local container.

Required fixture files:

* `/index.php`
  Normal page used as a seed.

* `/index.php.bak`
  Returns `200`, `Content-Type: text/plain`, body contains PHP-like source.

* `/.index.php.swp`
  Returns `200`, body contains editor-swap-like bytes or text.

* `/backup.zip`
  Returns `200`, `Content-Type: application/zip`, body starts with ZIP magic bytes. It can be a tiny harmless ZIP made for the fixture.

* `/dump.sql`
  Returns `200`, `Content-Type: text/plain`, body contains harmless SQL fixture data:

  * `CREATE TABLE`
  * `INSERT INTO`

* `/missing-anything.bak`
  Returns fixture 404.

* `/soft404/config.php.bak`
  Returns `200` with the same body as the fixture missing-page baseline. Must be rejected.

* `/spa/app.js.bak`
  Returns `200` with SPA fallback HTML. Must be rejected.

* `/forbidden/secret.zip`
  Returns `403`. Must not be confirmed.

* `/redirect/offscope.zip`
  Redirects to another host. Must not be followed.

* `/large/backup.tar.gz`
  Returns a large response. The runner must stop at the configured byte cap.

If reusing an existing fixture is preferred:

* `dvwa` can be extended with `/index.php.bak` and `/dump.sql`.
* `juice-shop` can be extended with `/backup.zip` and a soft-404 route.
* `webgoat` is less suitable for this spec unless the fixture already allows static files to be mounted predictably.

The preferred MVP fixture is `backup-files-lab` because it can cover source backup, archive, dump, editor swap, soft-404, forbidden, redirect, and large-response behavior without relying on an app’s real routes.

## Acceptance criteria

Implementation is acceptable when:

* It uses shared `ScanTarget` and `Evidence`.
* It defines only `BackupFileSignature` and `BackupFileFinding` as stub-specific types.
* Candidate generation is deterministic and bounded.
* Detection does not depend on hostname-specific assumptions.
* The runner uses only `HEAD` and `GET`.
* The runner follows only same-origin redirects.
* The runner rejects soft-404 and SPA fallback responses.
* The runner confirms exposed backup files only from response evidence.
* The runner classifies source backups, config backups, database dumps, archives, editor swap files, temporary copies, and unknown backup artifacts.
* Confidence is always one of `low`, `medium`, or `high`.
* Finding status is always one of `candidate`, `confirmed`, `rejected`, or `stale`.
* Response body collection is capped.
* Large files do not get fully downloaded.
* Archive files are not extracted.
* Raw secrets and large dumped content are not written to normal logs.
* The scan is idempotent across repeated runs.
* Duplicate findings are not created for the same normalized target URL and signature.
* TLS errors, timeouts, and connection failures are handled as probe errors, not crashes.
* Budget exhaustion is recorded in metrics.
* The runner completes within the configured candidate and timeout budget.
* Tests cover positive findings, soft-404 rejection, forbidden responses, off-scope redirects, large responses, duplicate prevention, and stale updates.
* AI is not called.

