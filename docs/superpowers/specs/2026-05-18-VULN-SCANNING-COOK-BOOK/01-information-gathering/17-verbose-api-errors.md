---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 17
slug: verbose-api-errors
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.17 Verbose API errors

> Phase 1 — Information gathering · Category: Error disclosure

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

Detect API error responses that expose implementation details such as exception names, stack frames, source paths, line numbers, SQL errors, framework debug pages, or internal service names. A runner cares because these responses help an attacker fingerprint the backend, map code paths, and tune later attacks without needing authenticated access.

## Inputs

The runner receives a shared `ScanTarget` and uses shared `Evidence` for stored observations.

Stub-specific inputs:

* `base_url`: inherited from `ScanTarget`.
* `known_endpoints`: optional list of URLs found by earlier discovery specs, especially routes under `/api`, `/rest`, `/graphql`, `/v1`, `/v2`, or routes that returned JSON.
* `optional_credentials`: only if the scan scope already allows authenticated browsing. The detector must not try credentials, guess credentials, or bypass login.
* `config`:

  * `timeout_seconds`, default `10`.
  * `max_api_error_probes_per_target`, default `30`.
  * `max_api_error_probes_per_endpoint`, default `3`.
  * `max_response_body_bytes`, default `65536`.
  * `max_evidence_excerpt_bytes`, default `4096`.
  * `allowed_methods`, default `GET`, `HEAD`, `OPTIONS`.
  * `follow_redirects`, default `false`; if enabled, follow only same-origin redirects.
  * `user_agent`, using the project scanner user agent.
  * `api_prefix_candidates`, default `api`, `rest`, `v1`, `v2`.
  * `skip_path_patterns`, including logout, signout, delete, destroy, admin actions, payment, checkout, upload, import, reset, and any project-wide denylist.
  * `redact_secrets`, default `true`.

The detector should prefer endpoints already seen during crawling. If no known API endpoints exist, it may probe a small set of common API prefixes with a non-existing route, but it must keep the probe count low.

## Detection logic

Detection is deterministic. The runner sends only safe read requests and classifies the resulting responses.

### Endpoint selection

Build a candidate set from:

* Routes discovered by the crawler that returned API-like content:

  * `application/json`
  * `application/problem+json`
  * `application/vnd.api+json`
  * XML API responses
  * plain text API errors
* Paths that look API-like:

  * `/api/...`
  * `/rest/...`
  * `/graphql`
  * `/v1/...`
  * `/v2/...`
* Routes found in JavaScript bundles, OpenAPI documents, sitemaps, or prior passive discovery.

Skip candidates when:

* The method would need `POST`, `PUT`, `PATCH`, or `DELETE`.
* The URL path or query suggests logout, deletion, payment, checkout, password reset, upload, import, admin mutation, or similar state change.
* The response is a binary asset.
* The endpoint is off-origin.
* The endpoint is outside the scan scope.
* The route requires payloads that would be mutating or exploit-like.

### Probe plan

For each selected endpoint, run at most the configured per-endpoint probe count.

Allowed probes:

1. Baseline safe request

   * Send the normal `GET` request.
   * Record status, content type, selected headers, response hash, and a redacted excerpt.
   * Do not flag a finding from status code alone.

2. Non-existing API sibling

   * For an API-like path, request a same-prefix route such as:

     * `/api/__scanner_nonexistent_<nonce>__`
     * `/rest/__scanner_nonexistent_<nonce>__`
   * The nonce must be short and harmless.
   * This probe is used to trigger framework 404 or route errors.

3. Invalid read parameter

   * On existing `GET` endpoints, append one harmless query parameter:

     * `scanner_probe=invalid`
   * Do not use SQL, script, template, shell, path traversal, or injection payloads.

4. Invalid path identifier

   * Only when an endpoint already contains a simple numeric or UUID-like path segment.
   * Replace one copied request with a harmless invalid ID, such as `not-a-valid-id`.
   * Keep the same method as the observed safe request.
   * Do not attempt enumeration.

5. `OPTIONS`

   * Only if `OPTIONS` is in `allowed_methods`.
   * Use it to observe API framework error handling and allowed methods.
   * Do not treat method exposure alone as a verbose API error.

Do not send request bodies for this spec.

### Response classification

Analyze only the received response evidence. Never hard-code a hostname to an expected technology.

A response is a confirmed verbose API error when it has an error status and at least one strong disclosure indicator.

Error status means:

* `400` to `599`, or
* `200` with a JSON body that clearly represents an API error object.

Strong disclosure indicators include:

* Stack trace fields:

  * `stack`
  * `trace`
  * `stackTrace`
  * `traceback`
  * `frames`
  * `backtrace`
* Exception fields:

  * `exception`
  * `exceptionClass`
  * `errorClass`
  * `type` with a framework exception value
* Source location fields:

  * `file`
  * `filename`
  * `line`
  * `lineNumber`
  * `column`
* Source paths:

  * `/app/`
  * `/srv/`
  * `/var/www/`
  * `/home/`
  * `C:\`
  * `D:\`
  * `node_modules/`
  * `vendor/`
  * `site-packages/`
  * `.py:`
  * `.js:`
  * `.ts:`
  * `.java:`
  * `.cs:`
  * `.php:`
  * `.rb:`
* Framework or runtime traces:

  * Python traceback text
  * Django debug details
  * Flask or Werkzeug debugger output
  * FastAPI, Starlette, Uvicorn, or SQLAlchemy exception output
  * Express or Node stack frames
  * NestJS exception traces
  * Java, Spring, Tomcat, Jetty, or Servlet exceptions
  * .NET developer exception pages
  * PHP Laravel, Symfony, Yii, or WordPress fatal errors
  * Ruby on Rails or Rack traces
  * Go panic traces
* Database error disclosure:

  * SQL syntax error
  * SQLSTATE
  * PostgreSQL error text
  * MySQL or MariaDB error text
  * SQLite error text
  * Oracle `ORA-` errors
  * MSSQL error text
  * MongoDB or Redis exception text
  * ORM exception names

Weak indicators include:

* Generic `message`, `error`, or `detail` fields.
* HTTP status text.
* Request IDs.
* RFC 7807 problem details without stack, trace, exception, file path, SQL, framework, or debug fields.
* Normal validation errors such as “field is required”.

Weak indicators alone are not enough for a finding.

### Confidence rules

Use deterministic scoring:

* `high`:

  * Error status plus stack trace, source path, exception class, or database error.
  * Multiple strong indicators in the same response.
* `medium`:

  * Error status plus one framework/runtime exception hint, but no full stack or path.
  * `200` response with a clear error object containing strong debug fields.
* `low`:

  * Possible verbose error wording but no clear source path, stack frame, exception class, or database error.
  * Keep as `candidate`, not `confirmed`, unless another probe confirms it.

### Status rules

* `confirmed`: strong indicator found in live response evidence.
* `candidate`: weak or partial disclosure that may need a later manual review.
* `rejected`: generic error, normal validation response, or harmless problem details.
* `stale`: the finding was previously confirmed but the current scan no longer reproduces it.

## Persistence

Use the shared `ScanTarget` and `Evidence` types from `../00-shared-schema.md`. Do not redefine them here.

Store one `Evidence` record per HTTP response used to support or reject the finding. The evidence should include the safe request metadata, response status, selected response headers, body hash, redacted excerpt, and truncation status.

Stub-specific types:

```json
{
  "VerboseApiErrorSignature": {
    "id": "uuid",
    "target_id": "uuid",
    "evidence_id": "uuid",
    "url": "string",
    "method": "GET | HEAD | OPTIONS",
    "probe_kind": "baseline | nonexistent_api_sibling | invalid_query_parameter | invalid_path_identifier | options",
    "status_code": "integer",
    "content_type": "string | null",
    "body_sha256": "string",
    "matched_indicators": ["string"],
    "disclosure_types": [
      "stack_trace",
      "exception_class",
      "source_path",
      "source_line",
      "framework_debug",
      "database_error",
      "internal_service_hint"
    ],
    "framework_hints": ["string"],
    "database_hints": ["string"],
    "exception_hints": ["string"],
    "file_path_hints": ["string"],
    "excerpt": "string",
    "confidence": "low | medium | high",
    "created_at": "ISO-8601"
  },
  "VerboseApiErrorFinding": {
    "id": "uuid",
    "target_id": "uuid",
    "signature_ids": ["uuid"],
    "evidence_ids": ["uuid"],
    "url": "string",
    "method": "GET | HEAD | OPTIONS",
    "status": "candidate | confirmed | rejected | stale",
    "confidence": "low | medium | high",
    "severity": "info | low | medium | high",
    "title": "Verbose API error disclosure",
    "summary": "string",
    "disclosure_types": ["string"],
    "matched_indicators": ["string"],
    "framework_hints": ["string"],
    "database_hints": ["string"],
    "first_seen_at": "ISO-8601",
    "last_seen_at": "ISO-8601",
    "ai_assistance": "none"
  }
}
```

Persistence rules:

* Deduplicate findings by `target_id`, normalized URL path, method, and disclosure type.
* Keep separate signatures for separate responses when they expose different details.
* Store only redacted excerpts, not full sensitive response bodies, unless the project’s secure evidence store explicitly allows full response storage.
* Redact cookies, authorization headers, access tokens, API keys, session IDs, CSRF tokens, emails, and obvious personal data before storing excerpts.
* Do not persist request bodies because this spec must not send any.
* If a previous finding no longer reproduces, mark it `stale` instead of deleting it.

## Safety

This detector is read-only.

Allowed methods:

* `GET`
* `HEAD`
* `OPTIONS`

Forbidden methods:

* `POST`
* `PUT`
* `PATCH`
* `DELETE`
* Any custom method that might change state

Payload restrictions:

* Do not send request bodies.
* Do not send SQL injection payloads.
* Do not send XSS payloads.
* Do not send template injection payloads.
* Do not send command injection payloads.
* Do not send path traversal payloads.
* Do not send oversized values.
* Do not fuzz with large wordlists.
* Do not attempt authentication bypass.
* Do not enumerate IDs beyond the single copied invalid-ID check.

PII and secret handling:

* Redact sensitive headers before logging or persistence.
* Redact obvious tokens and credentials from response excerpts.
* Truncate body excerpts.
* Keep the response hash so repeated findings can be correlated without storing full content.

AI involvement:

* `None`.
* There is no deterministic gap that needs AI for the MVP.
* A later version may use AI to summarize already-confirmed verbose errors for reporting, but AI must not decide detection, status, confidence, or severity.

## Pass/fail check

The implementation passes when all assertions below are true.

Positive assertions:

* Given an API response with status `500` and a JSON `stack` field, the detector creates a `confirmed` finding with `high` confidence.
* Given an API response with status `500`, an exception class, and a source file path, the detector creates a `confirmed` finding with `high` confidence.
* Given an API response with a SQL error such as `SQLSTATE` or a PostgreSQL/MySQL/SQLite error string, the detector creates a `confirmed` finding.
* Given an API response with framework debug output, the detector stores the matched framework hint.
* Given a confirmed finding, the stored evidence includes method, URL, status code, content type, body hash, matched indicators, and a redacted excerpt.
* Re-running the detector against the same response updates `last_seen_at` and does not create duplicate findings.

Negative assertions:

* A generic `404 Not Found` page must not create a finding.
* A generic JSON body such as `{"error":"not found"}` must not create a finding.
* RFC 7807 `application/problem+json` without stack, trace, exception, file path, database error, or framework debug data must not create a finding.
* Normal validation errors such as missing field messages must not create a finding unless they expose exception, stack, source, framework, or database internals.
* Request ID headers alone must not create a finding.
* Server header disclosure alone must not create a finding for this spec.
* A `2xx` documentation page containing example stack traces must not create a confirmed finding.
* The detector must not send `POST`, `PUT`, `PATCH`, or `DELETE`.
* The detector must not send request bodies.
* The detector must not use exploit payloads to trigger errors.
* The detector must not follow redirects off-origin.
* The detector must not store cookies, authorization headers, or raw secrets in evidence excerpts.
* The detector must not use AI to decide detection.

## Test fixtures

Primary fixture: `verbose-api-errors`.

Create a small fixture service with API-like routes that expose both vulnerable and safe behavior.

Suggested fixture behavior:

* `GET /api/items/not-a-valid-id`

  * Vulnerable mode returns `500` JSON with:

    * `exception`
    * `stack`
    * `file`
    * `line`
    * one source path such as `/app/main.py`
  * This should produce a `confirmed` finding with `high` confidence.

* `GET /api/sql-error`

  * Vulnerable mode returns `500` JSON or text containing a database error string.
  * This should produce a `confirmed` finding.

* `GET /api/problem`

  * Safe mode returns RFC 7807 `application/problem+json` with no debug data.
  * This must not produce a finding.

* `GET /api/validation`

  * Safe mode returns `400` JSON with normal field validation messages.
  * This must not produce a finding.

* `GET /api/__scanner_nonexistent_<nonce>__`

  * Vulnerable mode returns a framework route exception with a stack trace.
  * Safe mode returns a generic 404.

The fixture should support a simple environment flag such as `VERBOSE_API_ERRORS=true` so the same tests can cover vulnerable and fixed behavior.

Optional regression fixtures:

* `juice-shop`: use only if a stable read-only route in the container reliably returns verbose API error details. Do not hard-code expected technology by hostname.
* `webgoat`: use only if a stable read-only lesson route returns verbose API error details without authentication side effects.

## Acceptance criteria

Operational criteria:

* The detector is idempotent.
* The detector completes within the configured probe budget.
* The detector respects global scan scope and denylist rules.
* The detector uses only `GET`, `HEAD`, and `OPTIONS`.
* The detector sends no request bodies.
* The detector handles TLS errors, connection timeouts, invalid redirects, compressed responses, malformed JSON, large bodies, and unknown content types without crashing.
* The detector truncates large response bodies before analysis and persistence.
* The detector records enough evidence to reproduce the finding manually.
* The detector avoids duplicate findings across repeated scans.
* The detector marks old findings `stale` when they no longer reproduce.
* The detector has deterministic confidence and status assignment.
* The detector has unit tests for signature matching, false positives, redaction, deduplication, and probe limits.
* The detector has integration tests against the `verbose-api-errors` fixture in both vulnerable and safe modes.
* No test calls external internet services.
* No test depends on a real third-party API.
* No AI is called by this detector.

