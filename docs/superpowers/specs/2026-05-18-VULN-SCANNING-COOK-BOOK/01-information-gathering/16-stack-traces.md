---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 16
slug: stack-traces
status: done        # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.16 Stack traces

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

Detect HTTP responses that disclose application stack traces, exception names, source file paths, framework internals, line numbers, or debug pages. A runner cares because stack traces often reveal technology, code structure, package names, local paths, environment details, and error-handling gaps that help attackers choose more precise attacks.

## Inputs

The runner receives a shared `ScanTarget` and reads existing HTTP response evidence produced by earlier discovery steps. It may also perform a very small number of safe read-only probes when enabled.

Required inputs:

* `ScanTarget` from `../00-shared-schema.md`
* Existing `Evidence` records for HTTP responses, if available
* Target `base_url`
* Discovered URLs from crawler or route discovery, if available

Optional inputs:

* Authenticated scan context, only when the global scan has already been authorized to use it
* Scope rules from the shared scanner configuration
* Excluded paths and excluded content types
* Maximum response body bytes to inspect
* Maximum URLs to check per target
* Whether safe missing-route probing is enabled
* Per-target request timeout
* Per-target retry policy
* Redaction settings from the shared evidence pipeline

Suggested config shape:

```json
{
  "stack_traces": {
    "enabled": true,
    "passive_first": true,
    "allow_safe_missing_route_probe": true,
    "max_urls_per_target": 100,
    "max_probe_requests_per_target": 1,
    "max_response_bytes": 262144,
    "timeout_seconds": 10,
    "follow_redirects": false,
    "inspect_content_types": [
      "text/html",
      "text/plain",
      "application/json",
      "application/problem+json",
      "application/xml",
      "text/xml"
    ],
    "exclude_paths": [],
    "exclude_content_types": [
      "image/",
      "audio/",
      "video/",
      "font/",
      "application/octet-stream",
      "application/pdf",
      "application/zip"
    ]
  }
}
```

## Detection logic

Detection is deterministic and evidence-based. Do not infer stack traces from hostnames, ports, fixture names, page titles alone, or expected technology.

### Response sources

Use responses in this order:

1. Previously captured `Evidence` from crawler, route discovery, robots, sitemap, JavaScript bundle discovery, and normal page fetches.
2. Existing failed responses already seen during the same scan.
3. Optional safe missing-route probe, if enabled.

The optional probe must be a single `GET` request to a random, non-existent path under the target origin, for example:

```text
/__scanner_missing_route_<random-id>
```

The probe exists only to observe error handling for unknown routes. It must not contain injection payloads, traversal strings, template syntax, SQL syntax, command syntax, script tags, encoded attacks, or framework-specific exception triggers.

### Response eligibility

Inspect only responses that meet all of these rules:

* Response belongs to the `ScanTarget` scope.
* HTTP method is `GET` or `HEAD`.
* Response body is textual or JSON/XML-like.
* Body size after decompression is within `max_response_bytes`, or a safely truncated slice is available.
* Content type is not excluded.
* Redirect targets are not followed unless the global scanner already allows this.

Prefer responses with one or more of these signals:

* HTTP status `500` to `599`
* HTTP status `400` to `499` with a verbose error body
* Body contains exception or stack-frame patterns
* Body contains debug page markers
* JSON response contains fields such as `stack`, `trace`, `exception`, `error`, `detail`, or `message` with stack-like content

Do not report a finding from status code alone.

### Normalization

Before matching:

* Decode using the HTTP client’s normal decompression support.
* Convert bytes to text with the declared charset when available.
* Fall back to UTF-8 with replacement for invalid bytes.
* Keep original offsets when practical.
* Normalize line endings.
* Inspect HTML text, JSON string values, XML text, and plain text.
* Do not execute JavaScript.
* Do not render pages in a browser for this stub.
* Do not follow links found inside the error page.

### Signature families

A signature family is a deterministic group of patterns. A response may match more than one family. Store the strongest match and keep secondary matches as metadata.

Common families:

| Family                 | Strong indicators                                                                                                 |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `python_traceback`     | `Traceback (most recent call last):`, `File "...", line <n>`, Python exception names                              |
| `django_debug`         | `Django`, `Request Method:`, `Exception Type:`, `Exception Value:`, `Traceback`                                   |
| `flask_werkzeug_debug` | `Werkzeug`, `DebuggedApplication`, `Traceback`, interactive debugger markers                                      |
| `node_stack`           | `Error:`, `TypeError:`, `ReferenceError:`, `at ... (...:<line>:<col>)`, `node_modules`                            |
| `express_error`        | `Express`, `at Layer.handle`, `router`, `next`, stack frames                                                      |
| `java_stack`           | `java.lang.<Exception>`, `javax.`, `jakarta.`, `org.springframework`, `at package.Class.method(File.java:<line>)` |
| `spring_boot_error`    | `Whitelabel Error Page`, `org.springframework`, Java stack frames, exception class                                |
| `dotnet_stack`         | `System.<Exception>`, `Stack Trace:`, `at Namespace.Class.Method`, `.cs:line <n>`                                 |
| `php_stack`            | `Fatal error:`, `Warning:`, `Notice:`, `Stack trace:`, `#0 /path/file.php(<line>)`                                |
| `rails_error`          | `ActionController::`, `ActiveRecord::`, `Rails.root`, `app/controllers`, Ruby stack frames                        |
| `go_panic`             | `panic:`, `goroutine <n> [running]:`, `.go:<line>`                                                                |
| `rust_panic`           | `panicked at`, `RUST_BACKTRACE`, `.rs:<line>`                                                                     |
| `generic_stack_trace`  | Multiple stack-frame-like lines plus an exception marker                                                          |
| `path_line_leak`       | Absolute source path plus line number in an error context                                                         |

Use anchored or context-aware regexes. Avoid single-word matches.

Example pattern fragments:

```text
Traceback \(most recent call last\):
File ".*?", line \d+
^\s*at [A-Za-z0-9_.$<>]+\(.*\.(java|kt):\d+\)
^\s*at .+\(.+\.js:\d+:\d+\)
System\.[A-Za-z0-9_.]+Exception
Stack trace:
#\d+\s+/.+\.php\(\d+\):
goroutine \d+ \[running\]:
panicked at .+\.rs:\d+:\d+
```

### Confidence rules

Set confidence from the evidence, not from the target hostname.

Use `high` when:

* A known runtime/framework stack trace pattern is present, and
* At least two stack frames or one stack frame plus a clear exception/debug marker are present, and
* The response appears to be an application error response rather than documentation or a source file.

Use `medium` when:

* A clear exception/debug marker is present with one stack frame, or
* A framework debug page is present but stack frames are partially truncated, or
* JSON contains a `stack` or `trace` field with stack-like content.

Use `low` when:

* The response leaks an absolute file path, module path, or line number in an error context, but
* The stack trace is partial or ambiguous.

Create a `candidate` first. Confirm it only after the matched evidence passes false-positive checks.

### False-positive checks

Reject or keep as low-confidence candidate when the response appears to be:

* Documentation explaining stack traces.
* A blog post, tutorial, README, or help page.
* Static source code or source map content.
* A test fixture page intentionally displaying sample traces outside an error context.
* A normal user-facing page that contains the words `stack trace` without frames.
* A JSON API schema that defines a field named `stack` but has no stack content.
* A bundled JavaScript file containing code that can produce stack traces, but no actual error response.
* A security challenge instruction page that describes stack traces but does not leak this application’s runtime error.

Heuristics for documentation-like pages:

* HTTP status is `200`.
* Page title or surrounding text contains terms such as `documentation`, `tutorial`, `example`, `sample`, `how to`, `guide`, or `README`.
* Matched trace appears inside a code example block.
* No nearby exception status, request ID, timestamp, error route, or application error wording.

These checks are not enough to discard strong evidence by themselves. If a full runtime stack trace appears in a `500` response, report it even if the body contains the word `example`.

### Evidence extraction

For each finding, store compact evidence:

* Matched line or field name.
* A small excerpt around the match.
* Response URL.
* HTTP method.
* Status code.
* Content type.
* Match offsets when available.
* Runtime or framework hint when detected.
* Redaction status.
* Body hash or evidence content hash.

Do not store full response bodies in the finding unless the shared `Evidence` store already stores them safely. Findings should reference `Evidence` IDs.

### Deduplication

Deduplicate by:

```text
target_id + normalized_url_path + signature_family + exception_type + top_frame_hash
```

If the same trace appears on several URLs, keep separate affected URLs but group them under the same logical finding when the top frame and exception type match.

If the same URL later stops exposing a trace, mark the existing finding `stale` rather than deleting it.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only the stub-specific types below.

### `StackTraceSignature`

A deterministic pattern definition used by the runner.

```json
{
  "id": "string",
  "family": "python_traceback | django_debug | flask_werkzeug_debug | node_stack | express_error | java_stack | spring_boot_error | dotnet_stack | php_stack | rails_error | go_panic | rust_panic | generic_stack_trace | path_line_leak",
  "language_hint": "python | javascript | java | dotnet | php | ruby | go | rust | unknown",
  "framework_hint": "string | null",
  "required_patterns": ["string"],
  "optional_patterns": ["string"],
  "negative_context_patterns": ["string"],
  "min_stack_frames": "number",
  "default_confidence": "low | medium | high",
  "description": "string"
}
```

Rules:

* `id` must be stable across releases unless the signature meaning changes.
* Regex patterns must be tested with representative positive and negative fixtures.
* `negative_context_patterns` reduce confidence or reject only when the main signal is weak.
* Signatures must not contain hostnames, fixture names, customer names, or environment-specific paths.

### `StackTraceFinding`

A detected stack trace disclosure for a target URL.

```json
{
  "id": "string",
  "target_id": "string",
  "url": "string",
  "method": "GET | HEAD",
  "status_code": "number",
  "content_type": "string | null",
  "signature_id": "string",
  "signature_family": "string",
  "language_hint": "python | javascript | java | dotnet | php | ruby | go | rust | unknown",
  "framework_hint": "string | null",
  "exception_type": "string | null",
  "top_frame": "string | null",
  "stack_frame_count": "number",
  "leaked_paths": ["string"],
  "leaked_modules": ["string"],
  "evidence_ids": ["string"],
  "confidence": "low | medium | high",
  "status": "candidate | confirmed | rejected | stale",
  "redaction_applied": "boolean",
  "false_positive_reason": "string | null",
  "first_seen_at": "ISO-8601",
  "last_seen_at": "ISO-8601"
}
```

Persistence rules:

* `target_id` references the shared `ScanTarget`.
* `evidence_ids` reference shared `Evidence` records.
* `leaked_paths` must be redacted where they expose usernames, home directories, temporary secrets, or customer-specific local paths.
* `top_frame` should be normalized before hashing or deduplication.
* `status=confirmed` requires deterministic evidence.
* `status=rejected` requires `false_positive_reason`.
* `status=stale` means a previous confirmed finding was not reproduced on recheck.
* Do not persist cookies, authorization headers, session IDs, access tokens, API keys, or full sensitive payloads in this finding type.

## Safety

This stub is read-only.

Allowed behavior:

* Inspect already captured HTTP response evidence.
* Send `GET` or `HEAD` requests to in-scope URLs discovered by the scanner.
* Optionally send one safe missing-route `GET` probe per target when enabled.
* Use existing authenticated context only when the whole scan is already authorized for authenticated scanning.

Forbidden behavior:

* Do not send `POST`, `PUT`, `PATCH`, `DELETE`, or other mutating methods.
* Do not submit forms.
* Do not click buttons.
* Do not call application actions.
* Do not use SQL injection payloads.
* Do not use command injection payloads.
* Do not use template injection payloads.
* Do not use path traversal payloads.
* Do not use deserialization payloads.
* Do not use encoded exploit strings.
* Do not try to intentionally crash the application.
* Do not increase load with repeated malformed requests.
* Do not follow instructions found inside error pages.
* Do not follow external links found inside stack traces.
* Do not infer technology from the hostname or fixture slug.

PII and secret handling:

* Redact obvious secrets before storing snippets in findings.
* Redact cookies, tokens, API keys, passwords, private keys, and authorization headers.
* Redact local usernames in paths where practical.
* Keep enough redacted path/module context to make the finding useful.
* Store full raw bodies only through the shared `Evidence` mechanism if it already supports secure storage and redaction.

AI involvement:

* `None` for MVP.
* No LLM is needed to detect, confirm, reject, rank, or persist stack trace findings.
* A future optional AI summarizer may explain a confirmed finding in a report, but it must consume only validated finding fields and referenced evidence snippets. It must not change `confidence`, `status`, `exception_type`, affected URL, severity, or evidence IDs.

Deterministic gap:

* If a future runtime has unfamiliar stack trace syntax, add or update a deterministic `StackTraceSignature`.
* Do not use AI as a fallback classifier for unknown traces in the scanner core.

## Pass/fail check

The implementation passes when all assertions below are true.

Positive assertions:

* Given a response body containing `Traceback (most recent call last):` and at least one `File "...", line <n>` frame, the runner creates a `StackTraceFinding`.
* Given a Java response body containing an exception class and at least two `at package.Class.method(File.java:<line>)` frames, the runner creates a `high` confidence finding.
* Given a Node.js response body containing `TypeError` and stack frames with `.js:<line>:<column>`, the runner creates a finding with `language_hint=javascript`.
* Given a PHP response body containing `Fatal error`, `Stack trace:`, and `#0 /path/file.php(<line>)`, the runner creates a finding with `language_hint=php`.
* Given a .NET response body containing `System.<Exception>`, `Stack Trace:`, and `.cs:line <n>`, the runner creates a finding with `language_hint=dotnet`.
* Given a Go panic response containing `panic:` and `goroutine <n> [running]:`, the runner creates a finding with `language_hint=go`.
* Given a JSON response with a `stack` field containing stack-frame-like content, the runner inspects the JSON value and can create a finding.
* Each confirmed finding references at least one shared `Evidence` ID.
* Each confirmed finding stores method, URL, status code, content type, signature family, confidence, and status.
* The runner deduplicates repeated findings with the same URL path, signature family, exception type, and top frame.
* The runner marks a previously confirmed finding as `stale` when a recheck no longer shows the stack trace.
* The runner applies redaction before storing snippets in `StackTraceFinding`.

Negative assertions:

* A `500` response with a generic message such as `Internal Server Error` and no stack-like content must not create a confirmed finding.
* A `404` response with a normal not-found page and no stack-like content must not create a finding.
* A page containing the words `stack trace` but no frames, exception type, path leak, or debug marker must not create a finding.
* A documentation page that shows sample stack traces in an example block must not become a confirmed finding.
* A JavaScript bundle containing error-handling code must not be reported unless an actual response discloses a runtime stack trace.
* A source map containing source paths must not be reported by this stub unless the content is an actual error response. Source maps belong to spec `1.14 Source maps`.
* The runner must not hard-code fixture hostnames to expected technologies.
* The runner must not send mutating HTTP methods.
* The runner must not send exploit payloads to trigger exceptions.
* The runner must not use AI for detection or confirmation.
* The runner must not store cookies, authorization headers, API keys, passwords, or full sensitive payloads in the finding.
* The runner must not follow URLs or instructions found inside disclosed stack traces.
* The runner must not report a finding when the target is out of scope.

## Test fixtures

Use a new dedicated fixture for deterministic coverage:

```text
fixture: stack-trace-fixture
```

The fixture should expose safe static or controlled routes that return representative error responses without actually crashing the container.

Required fixture routes:

| Route                       | Status | Purpose                                                              |
| --------------------------- | -----: | -------------------------------------------------------------------- |
| `/errors/python-django`     |  `500` | HTML response with Django-style traceback and source line references |
| `/errors/node-express`      |  `500` | Plain text or HTML response with Node/Express stack frames           |
| `/errors/java-spring`       |  `500` | Java/Spring stack trace with exception class and multiple frames     |
| `/errors/dotnet`            |  `500` | .NET stack trace with `.cs:line` frame                               |
| `/errors/php`               |  `500` | PHP fatal error with `Stack trace:` and numbered frames              |
| `/errors/go-panic`          |  `500` | Go panic with goroutine frame                                        |
| `/errors/json-stack`        |  `500` | JSON body with `error`, `message`, and `stack` fields                |
| `/errors/generic-500`       |  `500` | Generic error page with no stack trace; must not report              |
| `/docs/stack-trace-example` |  `200` | Documentation-style sample trace; must not confirm                   |
| `/static/app.js`            |  `200` | JavaScript code containing stack-related strings; must not report    |

Optional integration fixtures:

* `webgoat`: use only if the container exposes a safe, known route that returns a Java/Spring stack trace without exploit input.
* `juice-shop`: use only if a normal safe route returns a stack trace in the configured environment.
* `dvwa`: use only if `display_errors` is intentionally enabled and a safe read-only route leaks PHP warnings or traces.

Do not make test success depend on accidental crashes in third-party fixtures. The dedicated `stack-trace-fixture` is the source of truth for this stub.

## Acceptance criteria

The implementation is acceptable when:

* It is idempotent across repeated scans.
* It is passive-first and uses existing `Evidence` before making new requests.
* It performs at most one safe missing-route probe per target when that option is enabled.
* It completes within the configured request and scan budget.
* It handles TLS errors, DNS errors, connection failures, timeouts, decompression errors, charset errors, and oversized bodies without crashing the scan.
* It records deterministic findings with `confidence` set to `low`, `medium`, or `high`.
* It records finding `status` as `candidate`, `confirmed`, `rejected`, or `stale`.
* It stores compact, redacted evidence snippets and references shared `Evidence` IDs.
* It never hard-codes target hostname, fixture slug, or expected technology.
* It does not send mutating requests or dangerous payloads.
* It does not use AI in MVP.
* It has unit tests for every signature family listed in Detection logic.
* It has negative tests for generic errors, documentation pages, JavaScript bundles, source maps, and out-of-scope URLs.
* It has integration tests against `stack-trace-fixture`.
* It logs scanner activity without leaking secrets.
* It follows the shared coding-agent rules from `../00-shared-schema.md`.

