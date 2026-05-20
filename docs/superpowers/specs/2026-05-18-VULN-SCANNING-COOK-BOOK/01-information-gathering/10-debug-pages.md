---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 10
slug: debug-pages
status: done        # pending | in-progress | blocked | done
fixture: dvwa       # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.10 Debug pages

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

Detect exposed debug, profiler, diagnostic, route-inspection, environment, and framework error pages using passive HTTP requests. These pages often leak stack traces, absolute paths, package versions, routes, environment variables, server metadata, request headers, or runtime settings. A runner cares because debug pages give strong follow-up signals for technology fingerprinting, attack-surface mapping, and risk triage without needing exploitation.

## Inputs

The runner receives a shared `ScanTarget` and reads `base_url`, `host`, and any existing target metadata from the shared schema.

Optional inputs:

* `http_client`: shared scanner HTTP client with timeout, redirect, TLS, and proxy settings.
* `credentials_ref`: optional authenticated session reference when the RoE allows authenticated testing.
* `candidate_paths`: optional paths discovered by earlier specs, such as robots.txt, sitemap, JavaScript route extraction, backup files, old endpoints, or admin panel discovery.
* `framework_hints`: optional hints from earlier fingerprinting specs. These may influence path ordering only. They must not create a finding by themselves.
* `max_requests`: default `60` per target for this spec.
* `max_response_bytes`: default `256000`.
* `timeout_seconds`: default `8`.
* `follow_redirects`: default `true`, but only within the same origin.
* `include_authenticated_paths`: default `false`; may be true only when the scanner session has an approved authenticated context.
* `path_wordlist_profile`: `minimal | standard | extended`, default `standard`.

The runner must not require credentials. If credentials are absent, it performs unauthenticated discovery only.

## Detection logic

Detection is deterministic. The runner sends read-only requests to known debug-page paths and to discovered candidate paths that look like debug, profiler, diagnostics, route, environment, or trace endpoints.

### Request method

Use `GET` by default.

`HEAD` may be used as a cheap pre-check only when the shared HTTP client already supports it, but a `HEAD` response alone must not confirm a debug page unless the headers are uniquely diagnostic. Many frameworks do not expose useful debug content through `HEAD`.

Allowed methods:

* `GET`
* `HEAD`

Forbidden methods:

* `POST`
* `PUT`
* `PATCH`
* `DELETE`
* `OPTIONS` unless already used by a shared safe crawler layer
* any method override header such as `X-HTTP-Method-Override`

### Candidate paths

Use a curated list and merge it with discovered paths. Normalize paths before requesting:

* collapse duplicate slashes after the scheme and host
* preserve case
* remove fragments
* keep query strings only when they came from discovered paths
* reject absolute off-origin URLs
* deduplicate by normalized path and query

Suggested built-in paths for the `standard` profile:

```text
/debug
/debug/
/debug/default/view
/debug/vars
/debug/pprof
/debug/pprof/
/debug/pprof/cmdline
/debug/pprof/goroutine
/_debug_toolbar/
/_debug_toolbar
/_profiler/
/_profiler
/_profiler/phpinfo
/_profiler/empty/search/results
/profiler
/profiler/
/phpinfo.php
/phpinfo
/info.php
/server-status
/server-status/
/server-info
/server-info/
/status
/status/
/actuator
/actuator/
/actuator/health
/actuator/info
/actuator/env
/actuator/configprops
/actuator/beans
/actuator/mappings
/actuator/threaddump
/actuator/heapdump
/actuator/prometheus
/routes
/routes/
/rails/info/routes
/rails/info/properties
/laravel/telescope
/telescope
/telescope/
/horizon
/_ignition/health-check
/_ignition/execute-solution
/__debugger__
/console
/console/
/werkzeug/console
/_next/static/development/_devMiddlewareManifest.json
/vite/client
/__vite_ping
```

Notes:

* Requesting `/_ignition/execute-solution` is allowed only as a `GET` probe. Do not submit solution payloads.
* Requesting `/actuator/heapdump` can return a very large body. The runner must apply `max_response_bytes`, stop reading after the limit, and mark the evidence as truncated.
* `/server-status` and `/server-info` may be legitimate internal-only pages. They are findings only when exposed to the scanned context.
* `/status` and `/health` are too generic to confirm debug exposure without strong body evidence.

### Response classification

For each response, classify it as one of:

* `not_found`: clear 404 or equivalent missing page
* `blocked`: 401, 403, or login redirect
* `generic`: page exists, but no debug evidence
* `candidate`: weak debug indicator
* `confirmed`: strong debug indicator
* `error`: network, TLS, timeout, parser, or scanner error

HTTP status alone is not enough to confirm a finding. A `200` page at `/debug` is only a candidate until the body or headers contain debug-specific evidence.

### Strong indicators

A response is `confirmed` when it has at least one strong indicator from a known debug surface, or a combination of medium indicators that uniquely identify a debug page.

Strong indicators include:

* PHP info page markers:

  * `<title>phpinfo()</title>`
  * `PHP Version`
  * `$_SERVER`
  * `Configuration File (php.ini) Path`
* Django debug toolbar markers:

  * `djDebug`
  * `__debug__`
  * `SQLPanel`
  * `HistoryPanel`
* Symfony profiler markers:

  * `_profiler`
  * `Symfony Profiler`
  * `sf-toolbar`
  * `X-Debug-Token`
  * `X-Debug-Token-Link`
* Spring Boot actuator markers:

  * JSON keys such as `"_links"`, `"self"`, `"health"`, `"env"`, `"beans"`, `"mappings"` on actuator paths
  * actuator media type or endpoint-specific structure
* Go pprof markers:

  * `Types of profiles available`
  * `goroutine`
  * `heap`
  * `threadcreate`
  * `cmdline`
* Werkzeug debugger markers:

  * `Werkzeug Debugger`
  * `Console Locked`
  * `__debugger__`
  * `PIN`
* Laravel debug or tooling markers:

  * `Laravel Telescope`
  * `Laravel Horizon`
  * `Ignition`
  * `Whoops`
  * `_ignition`
* Rails route/debug markers:

  * `Routes`
  * `Controller#Action`
  * `rails/info/routes`
  * `Rails::InfoController`
* Apache server status/info markers:

  * `Apache Server Status`
  * `Server Version: Apache`
  * `Current Time`
  * `Scoreboard Key`
  * `server-status`
* Stack trace markers with framework context:

  * `Traceback (most recent call last)`
  * `Stack trace:`
  * `Exception in thread`
  * `at org.`
  * `File "/`
  * `vendor/`
  * `node_modules/`
  * absolute project paths
* Environment/config leak markers:

  * `APP_ENV`
  * `DEBUG=True`
  * `NODE_ENV=development`
  * `DATABASE_URL`
  * `SECRET_KEY`
  * `AWS_ACCESS_KEY_ID`
  * `DB_PASSWORD`
  * `REDIS_URL`

Secret-like markers must be stored only as redacted snippets.

### Medium indicators

Medium indicators include:

* status `200` or `3xx` on a high-signal path such as `/debug/pprof/`, `/_profiler/`, `/phpinfo.php`, or `/rails/info/routes`
* debug-specific headers, such as:

  * `X-Debug-Token`
  * `X-Debug-Token-Link`
  * `X-Runtime`
  * `X-Powered-By` with debug body evidence
* body contains words such as `debug`, `profiler`, `trace`, `exception`, `stack`, `environment`, or `routes` on a matching path
* JSON response exposes endpoint names, configuration keys, route mappings, dependency names, or runtime details

Medium indicators must not confirm a finding by themselves unless at least two independent indicators are present.

### Low indicators

Low indicators include:

* path exists but body is generic
* redirect to login from a debug-looking path
* `401` or `403` on a high-signal debug path
* common words like `status`, `health`, or `info` without framework-specific evidence

Low indicators create `candidate` findings only when useful for follow-up. They should not be reported as confirmed vulnerabilities.

### Confidence rules

Use deterministic scoring:

* `high`: known debug page marker or endpoint-specific structure is present.
* `medium`: two or more medium indicators are present, or a debug-looking path is blocked but clearly exists.
* `low`: only weak indicators are present.

Finding status:

* `confirmed`: strong indicator, or enough medium indicators to identify the debug surface.
* `candidate`: weak or blocked evidence worth tracking.
* `rejected`: requested path is missing or generic.
* `stale`: previously confirmed path no longer reproduces on rescan.

### Redirect handling

Follow redirects only when the destination is same-origin.

Classify redirects:

* login redirect from debug path: `candidate`, confidence `low`
* redirect to a canonical debug path: continue classification on final response
* off-origin redirect: stop, record redirect metadata, do not follow
* redirect loop: stop after shared redirect limit and mark as `error`

### Evidence handling

For every requested candidate path, store a shared `Evidence` record when the result is `candidate`, `confirmed`, `blocked`, or `error`.

For `not_found` and generic negative results, store only compact telemetry unless the shared schema requires evidence for every request.

Evidence should include:

* request method
* normalized URL
* final URL after redirect
* HTTP status
* selected response headers
* content type
* body hash
* matched indicators
* short redacted snippet
* truncation flag
* scan timestamp
* authenticated/unauthenticated context flag

Do not persist full response bodies by default for pages that may contain secrets.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine either type here.

Define only the debug-page-specific signature and finding types.

```ts
export type DebugPageKind =
  | "phpinfo"
  | "django_debug_toolbar"
  | "symfony_profiler"
  | "spring_actuator"
  | "go_pprof"
  | "werkzeug_debugger"
  | "laravel_telescope"
  | "laravel_horizon"
  | "laravel_ignition"
  | "rails_info"
  | "apache_server_status"
  | "apache_server_info"
  | "stack_trace"
  | "environment_leak"
  | "route_listing"
  | "generic_debug"
  | "unknown";

export type DebugPageExposure =
  | "public"
  | "blocked"
  | "login_required"
  | "redirected"
  | "unknown";

export type DebugPageSignature = {
  id: string;
  name: string;
  kind: DebugPageKind;
  path_pattern: string;
  required_statuses?: number[];
  required_headers?: string[];
  required_body_patterns?: string[];
  medium_body_patterns?: string[];
  negative_body_patterns?: string[];
  confidence_if_matched: "low" | "medium" | "high";
  max_body_bytes_to_scan: number;
};

export type DebugPageFinding = {
  id: string;
  scan_target_id: ScanTarget["id"];
  evidence_ids: Evidence["id"][];

  url: string;
  final_url?: string;
  path: string;
  method: "GET" | "HEAD";
  status_code?: number;
  content_type?: string;

  kind: DebugPageKind;
  exposure: DebugPageExposure;

  matched_signature_ids: string[];
  matched_indicators: string[];
  redacted_snippet?: string;
  leaked_data_classes: Array<
    | "stack_trace"
    | "absolute_path"
    | "environment_variable"
    | "secret_like_value"
    | "package_version"
    | "route"
    | "runtime_config"
    | "request_header"
    | "server_status"
    | "unknown"
  >;

  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";

  first_seen_at: string;
  last_seen_at: string;
  checked_at: string;

  authenticated_context: boolean;
  truncated: boolean;
  notes?: string;
};
```

Persistence rules:

* Create or update one `DebugPageFinding` per `(scan_target_id, normalized path, kind, authenticated_context)`.
* Keep historical `first_seen_at`; update `last_seen_at` only when the finding still reproduces.
* Mark a previously confirmed finding as `stale` when the same path no longer returns matching evidence.
* Store raw response bodies only if the shared evidence store already supports protected sensitive evidence. Otherwise store a hash, matched indicators, and redacted snippets.
* Redact secret-like values before writing snippets:

  * API keys
  * tokens
  * passwords
  * cookies
  * authorization headers
  * private keys
  * database URLs
  * cloud credentials
* Link all findings to shared `Evidence` IDs.
* Do not create duplicate findings for the same final redirected debug page.

## Safety

This spec is read-only.

Allowed behavior:

* same-origin `GET`
* optional same-origin `HEAD`
* same-origin redirect following
* bounded response reads
* deterministic body/header matching
* redacted evidence persistence

Forbidden behavior:

* submitting forms
* clicking debug console buttons
* executing debugger commands
* sending framework-specific exploit payloads
* guessing Werkzeug PINs
* calling Ignition solution execution with payloads
* downloading full heap dumps beyond `max_response_bytes`
* brute forcing paths beyond the configured request budget
* following off-origin redirects
* using discovered credentials
* mutating server state
* changing application settings
* creating tickets, comments, or external notifications from raw findings

PII and secrets:

* Treat debug pages as likely sensitive.
* Do not store full bodies by default.
* Redact snippets before persistence.
* If a secret-like value is detected, store the data class and redacted proof, not the secret.
* Do not print full leaked values in logs.
* Do not include raw debug output in customer-facing reports unless the reporting layer has explicit secure evidence handling.

AI involvement: `None`.

Named deterministic gap:

* None for MVP. Debug-page detection is based on path, status, header, body, and JSON-structure signatures.
* If future work adds AI, it may only summarize already-redacted evidence for reporting. It must not classify the finding, decide severity, expand scope, choose new paths, or process raw unredacted debug output.

## Pass/fail check

The implementation passes when all assertions below are true.

Positive assertions:

* Given a page at `/phpinfo.php` containing `<title>phpinfo()</title>` and `PHP Version`, the runner creates a `DebugPageFinding` with:

  * `kind = "phpinfo"`
  * `status = "confirmed"`
  * `confidence = "high"`
  * at least one linked `Evidence` record
* Given a page at `/_profiler/` containing `Symfony Profiler` or `sf-toolbar`, the runner confirms a Symfony profiler finding.
* Given a JSON response at `/actuator/env` exposing environment property names, the runner confirms a Spring actuator finding without storing full secret values.
* Given `/debug/pprof/` containing `Types of profiles available`, the runner confirms a Go pprof finding.
* Given `/__debugger__` containing `Werkzeug Debugger`, the runner confirms a Werkzeug debugger finding.
* Given a debug-looking path returning `401` or `403`, the runner creates at most a `candidate` finding with `confidence = "low"` or `medium`, depending on path specificity.
* Given a same-origin redirect from `/debug` to `/_profiler/`, the runner follows the redirect and classifies the final page.
* Given a previously confirmed debug page that now returns 404 or generic content, the runner marks the existing finding as `stale`.
* Given a large response such as `/actuator/heapdump`, the runner stops reading at `max_response_bytes`, marks evidence as truncated, and still classifies based on available evidence if possible.
* Given secret-like values in debug output, the runner records redacted snippets and data classes.

Negative assertions:

* The runner must not send `POST`, `PUT`, `PATCH`, or `DELETE`.
* The runner must not submit payloads to `/_ignition/execute-solution`.
* The runner must not attempt to unlock or use the Werkzeug console.
* The runner must not guess debug console PINs or tokens.
* The runner must not follow off-origin redirects.
* The runner must not confirm `/status`, `/health`, or `/info` based on path and `200` status alone.
* The runner must not create a high-confidence finding from a generic 404 page that echoes the requested path.
* The runner must not store cookies, authorization headers, passwords, tokens, private keys, or database URLs in cleartext snippets.
* The runner must not hard-code hostnames to expected technologies.
* The runner must not let framework hints create findings without response evidence.
* The runner must not call an LLM for classification.
* The runner must not exceed `max_requests` for this spec.

## Test fixtures

Primary fixture: `debug-pages-lab`.

The fixture should expose deterministic endpoints for positive, candidate, stale, and negative cases.

Recommended fixture behavior:

```text
/phpinfo.php
  200 text/html with phpinfo-style markers and fake redacted-safe environment values.

/_profiler/
  200 text/html with Symfony profiler markers.

/_debug_toolbar/
  200 text/html with Django debug toolbar markers.

/actuator
  200 application/json with actuator _links.

/actuator/env
  200 application/json with fake environment keys and fake secret-like values.

/debug/pprof/
  200 text/html with Go pprof profile names.

/__debugger__
  200 text/html with Werkzeug debugger locked-console markers.

/rails/info/routes
  200 text/html with route table markers.

/server-status
  200 text/html with Apache server-status markers.

/debug-blocked
  403 text/html with no body secrets.

/debug-login
  302 redirect to /login.

/health
  200 application/json with {"status":"ok"} and no debug markers.

/debug-generic
  200 text/html with generic marketing or placeholder content.

/debug-missing
  404 text/html.

/actuator/heapdump
  200 application/octet-stream or large body exceeding max_response_bytes.
```

Secondary negative fixtures:

* `juice-shop`: run the standard path list and assert no confirmed debug-page finding unless the fixture image is intentionally modified to expose one.
* `dvwa`: use as a negative or low-signal fixture unless a debug endpoint is deliberately enabled for the test.
* `webgoat`: use as a negative or blocked-path fixture unless the container exposes actuator or diagnostic endpoints.

Fixture data must use fake secrets only, such as `FAKE_SECRET_DO_NOT_USE`, and tests must still verify redaction.

## Acceptance criteria

Operational criteria:

* The runner is idempotent across repeated scans.
* The runner completes within the configured request budget.
* The runner enforces `max_requests`, `timeout_seconds`, and `max_response_bytes`.
* The runner handles TLS errors, connection errors, timeouts, malformed headers, invalid encodings, and oversized bodies without crashing the scan.
* The runner follows only same-origin redirects.
* The runner deduplicates normalized paths and final redirected pages.
* The runner uses deterministic signatures only.
* The runner produces stable `DebugPageFinding` records linked to shared `Evidence`.
* The runner marks old findings as `stale` when evidence no longer reproduces.
* The runner redacts secret-like values before snippets are logged or persisted.
* The runner has unit tests for signature matching, redaction, redirect handling, response truncation, stale transitions, and negative generic pages.
* The runner has integration tests against `debug-pages-lab`.
* No test calls external networks.
* No test requires real credentials.
* No finding is confirmed from path, hostname, or framework hint alone.
