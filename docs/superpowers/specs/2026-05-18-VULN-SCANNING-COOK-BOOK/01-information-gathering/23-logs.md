---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 23
slug: logs
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.23 Logs

> Phase 1 — Information gathering · Category: Sensitive files

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

Detect publicly reachable log files exposed under web roots, static directories, backup locations, or predictable application paths. A runner cares because logs often contain stack traces, internal paths, usernames, email addresses, session IDs, bearer tokens, API keys, request bodies, database errors, IP addresses, admin routes, and timestamps that help an attacker map the system or reuse secrets.

## Inputs

The runner receives a shared `ScanTarget` from `../00-shared-schema.md`.

Required input:

* `ScanTarget.url`
* scan run ID from the shared runner context
* shared HTTP client with redirect, timeout, TLS, and byte-limit controls
* shared evidence store for `Evidence`

Optional config knobs:

| Name                               |         Type |           Default | Notes                                                                                                     |
| ---------------------------------- | -----------: | ----------------: | --------------------------------------------------------------------------------------------------------- |
| `logs.max_paths`                   |      integer |              `80` | Maximum candidate paths tested per target.                                                                |
| `logs.timeout_ms`                  |      integer |            `5000` | Per-request timeout.                                                                                      |
| `logs.max_response_bytes`          |      integer |           `65536` | Hard cap for stored body excerpt.                                                                         |
| `logs.follow_redirects`            |      boolean |           `false` | Redirects can hide false positives. Keep disabled unless the shared runner enables same-origin redirects. |
| `logs.allow_same_origin_redirects` |      boolean |            `true` | Only used if redirects are enabled.                                                                       |
| `logs.methods`                     | string array | `["GET", "HEAD"]` | No mutating methods.                                                                                      |
| `logs.include_extensions`          | string array |         see below | Candidate log-like extensions.                                                                            |
| `logs.exclude_paths`               | string array |              `[]` | User or RoE supplied exclusions.                                                                          |
| `logs.redact_secrets`              |      boolean |            `true` | Apply shared redaction before display/logging.                                                            |
| `logs.confirm_with_get_after_head` |      boolean |            `true` | If `HEAD` looks interesting, confirm with bounded `GET`.                                                  |
| `logs.min_log_line_hits`           |      integer |               `2` | Minimum line-pattern hits for body-based confirmation unless a strong signature is found.                 |

Candidate extensions:

```text
.log
.logs
.log.txt
.out
.err
.trace
.audit
.debug
.access
.error
```

Candidate paths should be generated from the target base URL without assuming technology from the hostname.

Default path set:

```text
/logs
/logs/
/log
/log/
/debug.log
/error.log
/access.log
/application.log
/app.log
/server.log
/web.log
/trace.log
/audit.log
/events.log
/request.log
/requests.log
/http.log
/nginx.log
/apache.log
/apache2.log
/php_errors.log
/php-error.log
/laravel.log
/django.log
/uwsgi.log
/gunicorn.log
/celery.log
/node.log
/npm-debug.log
/yarn-error.log
/pnpm-debug.log
/debug/log
/admin/logs
/admin/log
/system.log
/storage/logs/laravel.log
/var/log/app.log
/var/log/error.log
```

The implementation may add fixture-specific paths only in fixture configuration, not in the detector core.

## Detection logic

Detection is deterministic and read-only.

### Request strategy

For each candidate path:

1. Normalize the target origin and join the candidate path safely.
2. Skip paths matching `logs.exclude_paths`.
3. Send `HEAD` first when supported by the shared HTTP client.
4. If `HEAD` returns a candidate status or useful metadata, send a bounded `GET`.
5. If `HEAD` returns `405`, `403`, or no useful metadata, optionally send a bounded `GET` only if the path is in the configured candidate list.
6. Store at most `logs.max_response_bytes` of response body as evidence.
7. Do not request byte ranges unless the shared HTTP client already supports safe range requests. If range requests are used, request only the first chunk.
8. Do not crawl links found inside logs.
9. Do not derive new paths from log content.
10. Do not retry with path traversal, encoded traversal, null bytes, shell metacharacters, or query-string payloads.

Allowed methods:

```text
HEAD
GET
```

Disallowed methods:

```text
POST
PUT
PATCH
DELETE
OPTIONS
TRACE
CONNECT
```

### Candidate response filter

A response is a candidate when at least one of these is true:

* HTTP status is `200`.
* HTTP status is `206` and the shared client intentionally used a safe range request.
* HTTP status is `403` and the response strongly identifies a log resource by path, filename, content type, or server message.
* HTTP status is `401` and the path strongly identifies a log resource.
* `Content-Type` suggests plain text, log text, octet stream, or unknown content.
* `Content-Disposition` filename has a log-like extension.
* The URL path has a log-like filename and the response is not a generic HTML error page.

Reject response as non-finding when any of these is true:

* status is `404`, `410`, or another clear not-found response
* body is a generic web app shell with no log indicators
* body is a login page
* body is a directory index without log file content
* body is JSON/HTML from an unrelated API route with no log indicators
* response is identical to the target’s known soft-404 baseline
* response body is empty and there is no strong filename, content type, or access-control signal

### Strong log indicators

A body confirms exposed log content when it contains enough log-like evidence.

Strong single-hit indicators:

```regex
(?im)^\[[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}
(?im)^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}[,.][0-9]{3}
(?im)^\[[A-Z]+\]\s+[0-9]{4}-[0-9]{2}-[0-9]{2}
(?im)\b(?:ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL|CRITICAL)\b.*\b(?:Exception|Traceback|stack|request|response|sql|database|token|session)\b
(?im)\bTraceback \(most recent call last\):
(?im)\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\/[^\s]*\s+HTTP\/[0-9.]+
(?im)\b(?:SQLSTATE|PDOException|QueryException|IntegrityError|OperationalError|DatabaseError)\b
(?im)\b(?:UnhandledPromiseRejection|TypeError|ReferenceError|SyntaxError):\b
(?im)\b(?:at\s+[A-Za-z0-9_.$<>]+\s+\([^)]*:[0-9]+:[0-9]+\)|File ".+", line [0-9]+, in .+)\b
```

Weak indicators. Require at least `logs.min_log_line_hits` across separate lines unless paired with a strong filename or log content type:

```regex
(?im)\b(?:ERROR|WARN|WARNING|INFO|DEBUG|TRACE|FATAL|CRITICAL)\b
(?im)\b(?:exception|stack trace|request id|correlation id|trace id)\b
(?im)\b(?:127\.0\.0\.1|localhost|client_ip|remote_addr|user_agent)\b
(?im)\b(?:started|completed|handled|listening|connected|disconnected)\b
(?im)\b(?:stdout|stderr|worker|process|thread|pid)\b
```

Sensitive-data indicators increase severity and confidence but are not required to confirm that a log file is exposed:

```regex
(?im)\b(?:authorization|bearer|api[_-]?key|secret|token|session|cookie|password|passwd|pwd)\b\s*[:=]
(?im)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b
(?im)\b(?:AKIA|ASIA)[A-Z0-9]{16}\b
(?im)\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b
(?im)\b(?:postgres|mysql|mongodb|redis|amqp|ldap|s3)://[^\s'"<>]+
(?im)\b(?:/home/[A-Za-z0-9_.-]+|/var/www/[^\s:]+|C:\\\\[A-Za-z0-9_ .-]+\\\\[^\s:]+)\b
```

### Content-type handling

Treat these as compatible with log content:

```text
text/plain
text/x-log
application/octet-stream
application/log
application/x-log
binary/octet-stream
```

Do not require a specific content type. Many exposed logs are served as `text/plain`, `application/octet-stream`, or with no content type.

Treat `text/html` as suspicious only when the body itself matches log indicators. Do not flag a normal HTML error page only because the requested path ends in `.log`.

### Baseline soft-404 handling

Before confirming a finding, compare candidate responses with the shared runner’s soft-404 baseline when available.

A candidate must not be confirmed when:

* status, content length, title, and body hash are close to the known soft-404 baseline
* the same body appears for multiple random non-existent `.log` paths
* response contains common not-found phrases and no log indicators

Recommended baseline check:

```text
/__scanner_nonexistent_<random>.log
```

Only use this if the shared runner already permits one safe baseline request per target. Do not add noisy baseline probes if the project has a global baseline mechanism.

### Confidence rules

Use `high` confidence when:

* status is `200` or `206`
* body has a strong log indicator
* body is not a soft-404
* evidence includes a log path, log content type, or log-like filename

Use `medium` confidence when:

* status is `200`
* body has multiple weak log indicators
* response is not a known soft-404
* sensitive data is not required but may be present

Use `low` confidence when:

* status is `401` or `403` on a strongly log-like path
* no body is available
* metadata suggests a log resource but content is not readable
* the body is truncated before enough indicators are found

Do not create a confirmed finding with `low` confidence. Persist it as `candidate` unless the project’s shared policy says otherwise.

### Status rules

* `confirmed`: readable exposed log content was retrieved and deterministic indicators matched.
* `candidate`: metadata strongly suggests a log resource, but the body is unavailable, blocked, empty, or truncated before confirmation.
* `rejected`: response was tested and did not match.
* `stale`: a previously confirmed finding no longer reproduces on rescan.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only stub-specific types.

```ts
export type LogsConfidence = "low" | "medium" | "high";
export type LogsFindingStatus = "candidate" | "confirmed" | "rejected" | "stale";

export interface LogsSignature {
  id: string;
  name: string;
  path: string;
  method: "HEAD" | "GET";
  expected_statuses: number[];
  log_path_hint: boolean;
  strong_body_patterns: string[];
  weak_body_patterns: string[];
  sensitive_body_patterns: string[];
  allowed_content_types: string[];
}

export interface LogsFinding {
  target: ScanTarget;
  evidence: Evidence[];

  signature_id: string;
  url: string;
  path: string;
  method: "HEAD" | "GET";
  status_code: number | null;

  status: LogsFindingStatus;
  confidence: LogsConfidence;

  content_type: string | null;
  content_length: number | null;
  body_excerpt_bytes: number;
  body_truncated: boolean;

  matched_strong_indicators: string[];
  matched_weak_indicators: string[];
  matched_sensitive_indicators: string[];

  soft_404_checked: boolean;
  soft_404_match: boolean;

  readable: boolean;
  access_blocked: boolean;

  secret_redaction_applied: boolean;
  pii_redaction_applied: boolean;

  created_at: string;
  updated_at: string;
}
```

Persistence requirements:

* Store one finding per unique normalized URL and signature ID.
* Store request and response metadata in shared `Evidence`.
* Store only bounded, redacted body excerpts.
* Store body hash before and after redaction if the shared evidence model supports both.
* Do not store full logs outside the secure evidence store.
* Do not duplicate the same log file across repeated candidate paths after redirects or normalization.
* Preserve enough data for audit:

  * URL
  * method
  * status
  * content type
  * content length
  * excerpt hash
  * matched indicators
  * truncation flag
  * redaction flag

Suggested evidence labels:

```text
logs.request
logs.response.head
logs.response.body_excerpt
logs.match.strong_indicator
logs.match.weak_indicator
logs.match.sensitive_indicator
logs.soft404
```

## Safety

This check is read-only.

Allowed behavior:

* Send bounded `HEAD` and `GET` requests to configured candidate paths.
* Follow same-origin redirects only if enabled by shared runner policy.
* Read at most `logs.max_response_bytes`.
* Store only redacted excerpts and metadata.
* Use deterministic pattern matching.
* Mark blocked log-like paths as `candidate`, not `confirmed`.

Forbidden behavior:

* No mutating HTTP methods.
* No path traversal payloads.
* No brute-force wordlists beyond the configured path budget.
* No authentication attempts.
* No credential reuse.
* No crawling from log contents.
* No fetching URLs found inside logs.
* No query-string fuzzing.
* No attempts to bypass access controls.
* No decompression bombs. Respect shared size and decompression limits.
* No full-log download when the content is large.
* No AI interpretation of raw log bodies by default.

Payload restrictions:

* Paths must be static candidates or fixture-defined candidates.
* Paths must not contain traversal sequences such as `../`, `%2e%2e`, `%252e`, or mixed-encoded variants.
* Paths must not include shell metacharacters.
* Paths must not include user-controlled values scraped from the target.

PII and secret handling:

* Apply shared redaction before displaying or writing body excerpts to non-secure logs.
* Redact common token, cookie, authorization, password, connection-string, and API-key patterns.
* Keep matched sensitive indicator names, not raw secret values.
* Show only small snippets around matched indicators if the UI needs context.
* Do not print raw log lines in test output.

AI involvement: `None`.

Deterministic gap:

* If a future version needs to classify unusual proprietary log formats that do not match known patterns, it may add an AI-assisted `candidate_review` step.
* That step must use redacted excerpts only.
* It must not change `confirmed` status without deterministic evidence.
* It must be documented in this section before implementation.

## Pass/fail check

The implementation passes when all assertions below are true.

### Positive assertions

* Given a target exposing `/debug.log` with timestamped `ERROR` lines, the scanner creates one `LogsFinding`.
* The finding has `status = "confirmed"`.
* The finding has `confidence = "high"` when a strong log indicator matches.
* The finding references at least one shared `Evidence` item.
* The evidence contains request URL, method, status code, response headers, body excerpt hash, and truncation status.
* The finding records the matched strong indicator ID or pattern name.
* The scanner applies the configured byte cap to the response body.
* The scanner marks `body_truncated = true` when the body exceeds the cap.
* The scanner applies secret redaction before exposing snippets in normal logs or UI output.
* A readable log containing `Authorization: Bearer <value>` records a sensitive indicator without exposing the raw token in normal output.
* A `403` response on `/logs/app.log` becomes `candidate` with `low` confidence when no body is readable but the path strongly suggests a log resource.
* A repeated scan updates the existing finding instead of creating duplicates.
* If a previously confirmed log returns `404` on rescan, the finding becomes `stale`.

### Negative assertions

* The scanner must not confirm a finding for a normal `404` response.
* The scanner must not confirm a finding for a soft-404 page that is reused for random missing `.log` paths.
* The scanner must not confirm a finding for a login page served from `/logs`.
* The scanner must not confirm a finding for a generic HTML shell with no log indicators.
* The scanner must not treat hostname, brand, or target name as proof of a technology stack.
* The scanner must not assume `/storage/logs/laravel.log` exists because a host appears to run PHP.
* The scanner must not use `POST`, `PUT`, `PATCH`, `DELETE`, `TRACE`, or `CONNECT`.
* The scanner must not attempt path traversal such as `/../../var/log/app.log`.
* The scanner must not fetch URLs discovered inside log content.
* The scanner must not store full large log files in normal application logs.
* The scanner must not print raw secrets in test output.
* The scanner must not call an LLM.
* The scanner must not downgrade a confirmed readable log to rejected because sensitive patterns are absent.
* The scanner must not retry endlessly after timeouts.
* The scanner must not exceed `logs.max_paths`.

### Example test matrix

| Scenario                                               | Expected status | Expected confidence |
| ------------------------------------------------------ | --------------: | ------------------: |
| `/debug.log` contains timestamped stack trace          |     `confirmed` |              `high` |
| `/access.log` contains HTTP request lines              |     `confirmed` |              `high` |
| `/app.log` contains several weak log lines             |     `confirmed` |            `medium` |
| `/logs/app.log` returns `403`                          |     `candidate` |               `low` |
| `/debug.log` returns generic 404                       |      `rejected` |               `low` |
| `/debug.log` returns login page                        |      `rejected` |               `low` |
| `/npm-debug.log` contains package-manager error output |     `confirmed` |            `medium` |
| `/error.log` contains bearer token                     |     `confirmed` |              `high` |

## Test fixtures

Preferred fixture: `juice-shop`.

Use a small fixture extension if Juice Shop does not expose a suitable log file by default.

Fixture slug recommendation:

```text
logs-exposed
```

Fixture behavior:

* Container serves a normal app route.
* Container exposes `/debug.log` with deterministic log content.
* Container exposes `/access.log` with deterministic HTTP access-log lines.
* Container exposes `/logs/app.log` returning `403`.
* Container serves `/missing.log` as a real `404`.
* Container serves `/fake.log` as a soft-404 page if the shared runner supports soft-404 tests.
* Container serves `/login` and `/logs` as HTML login-like pages with no log indicators.
* Container exposes `/error.log` containing redaction test data.

Required fixture files:

```text
fixtures/logs-exposed/debug.log
fixtures/logs-exposed/access.log
fixtures/logs-exposed/error.log
fixtures/logs-exposed/app.py
fixtures/logs-exposed/README.md
```

Example `debug.log` content:

```text
[2026-05-19 09:12:33] ERROR app.request Traceback (most recent call last):
File "/var/www/app/views.py", line 42, in get
DatabaseError: connection refused
request_id=abc-123 user_agent="scanner-test"
```

Example `access.log` content:

```text
127.0.0.1 - - [19/May/2026:09:12:33 +0000] "GET /admin HTTP/1.1" 401 512 "-" "Mozilla/5.0"
127.0.0.1 - - [19/May/2026:09:12:34 +0000] "POST /login HTTP/1.1" 403 128 "-" "Mozilla/5.0"
```

Example `error.log` content:

```text
2026-05-19T09:12:33.123Z ERROR payment failed request_id=req-123
Authorization: Bearer test_token_must_be_redacted
DATABASE_URL=postgres://user:password@example.internal:5432/app
```

The fixture must be deterministic:

* no current timestamps generated at runtime
* no random ports in expected output
* no external network calls
* no dependency on real secrets
* no host-specific paths outside the fixture text

If using `dvwa` or `webgoat`, add a fixture note explaining the exact route or mounted file that exposes the log. Do not make the detector depend on that fixture name.

## Acceptance criteria

Operational quality bar:

* Uses shared `ScanTarget` and `Evidence`.
* Defines only `LogsSignature` and `LogsFinding` as stub-specific types.
* Runs without AI.
* Uses only deterministic response metadata and body pattern matching.
* Uses only `HEAD` and bounded `GET`.
* Has a hard path budget.
* Has a hard response byte budget.
* Has per-request timeout handling.
* Handles TLS errors through shared runner behavior.
* Handles connection refused, DNS failure, timeout, and invalid response without crashing the scan.
* Handles compressed responses through the shared client’s safe decompression limits.
* Handles binary or non-UTF-8 bodies by storing metadata and a safe decoded excerpt where possible.
* Handles redirects according to shared runner policy.
* Handles soft-404 baselines when available.
* Is idempotent across repeated scans.
* Produces stable finding IDs from target, normalized URL, and signature ID.
* Does not create duplicate findings for the same normalized log URL.
* Does not exceed configured retry limits.
* Does not perform flaky retries after deterministic `404`.
* Redacts secrets before normal logging or UI display.
* Preserves enough evidence for audit without storing full sensitive logs in normal output.
* Includes unit tests for matcher logic.
* Includes integration tests against the selected fixture.
* Includes negative tests for soft-404, login page, generic HTML, and empty body.
* Includes method-discipline tests proving no mutating methods are used.
* Includes budget tests proving `logs.max_paths` and `logs.max_response_bytes` are enforced.
* Completes within the Phase 1 scan budget used by the shared runner.

