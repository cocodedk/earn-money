---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 4
slug: backend-hints
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.4 Backend hints

> Phase 1 — Information gathering · Category: Technology fingerprinting

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

Detect backend technology hints from passive HTTP evidence and a small set of safe read-only probes. The runner helps later modules choose better checks without guessing, for example whether the target looks like Express, Django, Spring Boot, ASP.NET, Laravel, Rails, Flask, nginx proxying to an app server, or a generic API backend.

This spec does not prove the exact backend stack. It records bounded hints with confidence, evidence, and match reasons.

## Inputs

The runner receives:

* `ScanTarget` from `../00-shared-schema.md`.
* Existing `Evidence` records from earlier phase-1 runners, especially:

  * homepage response
  * redirect chain responses
  * server header evidence
  * frontend framework evidence
  * static asset responses
  * API response samples, if already collected
* Optional credentials from the scan context, only if the active RoE profile allows authenticated read-only testing.
* Runner config:

  * `max_requests`: default `8`
  * `timeout_seconds`: default `8`
  * `follow_redirects`: default `true`
  * `max_body_bytes`: default `65536`
  * `allow_diagnostic_paths`: default `true`
  * `allow_options_probe`: default `true`
  * `user_agent`: project default scanner UA
  * `respect_robots_for_diagnostic_paths`: default `false` for security testing targets, but configurable
  * `capture_error_pages`: default `true`
  * `persist_negative_evidence`: default `true`

The runner must not require a hostname-specific expected result. All findings come from observed responses.

## Detection logic

Detection is deterministic and evidence-based.

### Request plan

Use existing evidence first. Only send new requests when the needed signal is missing.

Allowed unauthenticated probes:

| Probe                       | Method                  | Purpose                                                    |
| --------------------------- | ----------------------- | ---------------------------------------------------------- |
| `/`                         | `GET` or reuse existing | Baseline headers, body, cookies, redirects                 |
| `/favicon.ico`              | `GET` or reuse existing | Framework or default app asset hints                       |
| `/robots.txt`               | `GET`                   | App/server style, generator comments, disallowed API roots |
| `/sitemap.xml`              | `GET`                   | Route style and backend-generated XML hints                |
| `/api`                      | `GET`                   | API shape and default error format                         |
| `/api/`                     | `GET`                   | API shape and redirect behavior                            |
| `/.well-known/security.txt` | `GET`                   | Contact metadata only, not backend proof                   |
| `/nonexistent-{random}`     | `GET`                   | 404 body, framework error page, routing style              |
| `/`                         | `OPTIONS`               | Allowed methods and CORS/API hints, if enabled             |

Rules:

* Use a random non-existing path with a short safe token, for example `/__scanner_backend_hint_404_{nonce}`.
* Do not request common admin paths such as `/admin`, `/wp-admin`, `/actuator`, `/debug`, `/phpinfo.php`, `/server-status`, `/console`, or framework debug endpoints in this spec.
* Do not brute-force paths.
* Do not send payloads.
* Do not submit forms.
* Do not attempt login.
* Do not infer backend from DNS names, company names, or target hostname.

### Evidence sources

Use these response parts:

* Status code
* Final URL
* Redirect chain
* Response headers
* Cookie names and attributes
* Body snippets
* Error page structure
* Static asset paths
* API error format
* CORS and `Allow` headers
* HTML comments only as low-confidence hints unless supported by stronger evidence
* Header/body mismatches as separate notes, not forced conclusions

### Signature matching

The runner loads built-in deterministic signatures. Each signature describes one backend hint.

A signature can match:

* exact header name/value
* header value regex
* cookie name regex
* body regex
* error-page regex
* path/URL pattern from observed links or script sources
* JSON error field shape
* status/redirect behavior
* multiple conditions joined with `all` or `any`

Every match must record:

* signature ID
* matched field
* matched value snippet or hash
* evidence ID
* response URL
* confidence contribution
* reason

### Example backend hints

#### Express / Node.js

Signals:

* `X-Powered-By: Express`
* Express default error page text
* `connect.sid` cookie
* JSON error body with common Express middleware shape
* Stack trace mentioning `node_modules` or Express, only if exposed in body

Confidence:

* `high`: explicit `X-Powered-By: Express`
* `medium`: Express default error page plus Node-style cookie
* `low`: only route/API shape resembles Express

#### Django

Signals:

* `csrftoken` cookie
* `sessionid` cookie with Django-like behavior
* Django debug page markers, if accidentally exposed
* `403 CSRF verification failed` body
* Admin/static path hints from observed links, not probed admin paths

Confidence:

* `high`: Django debug or CSRF error marker
* `medium`: `csrftoken` and `sessionid` with matching response behavior
* `low`: only `/static/admin/` asset references

#### Flask / Werkzeug

Signals:

* Werkzeug debugger markers, if exposed
* `werkzeug` in server or error body
* Flask default session cookie shape
* Python traceback markers from response body

Confidence:

* `high`: Werkzeug debugger/error page marker
* `medium`: Flask session cookie plus Werkzeug/Python error body
* `low`: only generic Python traceback markers

#### Spring Boot / Java

Signals:

* Whitelabel Error Page
* JSON error body with `timestamp`, `status`, `error`, `path`
* `JSESSIONID`
* Spring-specific headers or actuator links already present in discovered content

Confidence:

* `high`: Whitelabel Error Page or Spring Boot JSON error shape
* `medium`: `JSESSIONID` plus Java/Spring error format
* `low`: only generic Java servlet hints

#### ASP.NET / ASP.NET Core

Signals:

* `ASP.NET_SessionId`
* `.AspNetCore.*` cookies
* `X-AspNet-Version`
* `X-AspNetMvc-Version`
* ASP.NET error page markers
* Kestrel header, if present

Confidence:

* `high`: explicit ASP.NET headers or cookies
* `medium`: ASP.NET Core cookie plus error page style
* `low`: only Kestrel/proxy hints

#### Laravel / PHP

Signals:

* `laravel_session`
* `XSRF-TOKEN`
* Laravel error page markers
* PHP session cookie with Laravel body hints
* `X-Powered-By: PHP` as PHP runtime only, not Laravel proof

Confidence:

* `high`: `laravel_session` or Laravel error marker
* `medium`: `XSRF-TOKEN` plus Laravel-shaped error/body
* `low`: only PHP runtime evidence

#### Rails / Ruby

Signals:

* `_session` cookie with Rails naming pattern
* Rails error page markers
* `X-Runtime`
* asset paths resembling Rails packs/assets when supported by body evidence

Confidence:

* `high`: Rails error marker
* `medium`: Rails cookie pattern plus `X-Runtime`
* `low`: only asset naming hints

#### Generic API backend

Signals:

* JSON 404/405 responses
* consistent API error envelope
* CORS headers
* `Allow` header from `OPTIONS`
* `/api` or `/api/` returns structured JSON error

Confidence:

* `high`: repeated consistent JSON API errors across two endpoints
* `medium`: one JSON API error plus CORS/Allow evidence
* `low`: one API-shaped response only

### Conflict handling

When signatures conflict:

* Keep all plausible candidates.
* Do not collapse them into one winner unless one has explicit high-confidence evidence.
* Mark reverse-proxy and app-server hints separately.
* If a proxy header points to nginx but body/cookie evidence points to Django, create separate findings:

  * `nginx` as `role: reverse_proxy_or_web_server`
  * `django` as `role: application_framework`
* If evidence is stale or replaced by later evidence from the same URL, set the older finding status to `stale`.

### Confidence rules

Use `high` when the evidence explicitly names the backend or framework.

Use `medium` when two or more independent weak signals point to the same backend.

Use `low` when the signal is plausible but not enough for a direct claim.

Never produce `confirmed` from one weak hint.

### Status rules

* `candidate`: plausible but not enough to treat as reliable.
* `confirmed`: explicit signal or multiple independent strong signals.
* `rejected`: a prior candidate was disproven by newer or stronger evidence.
* `stale`: evidence was replaced by a newer scan result for the same target and signal.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only these stub-specific types.

```ts
type BackendHintSignature = {
  id: string;
  name: string;
  backend_family:
    | "nodejs"
    | "python"
    | "java"
    | "dotnet"
    | "php"
    | "ruby"
    | "go"
    | "generic_api"
    | "unknown";
  technology: string;
  role:
    | "application_framework"
    | "runtime"
    | "reverse_proxy_or_web_server"
    | "api_style"
    | "session_layer"
    | "unknown";
  match_scope:
    | "header"
    | "cookie"
    | "body"
    | "json"
    | "error_page"
    | "redirect"
    | "asset_path"
    | "method_behavior";
  matcher: {
    type: "exact" | "case_insensitive_exact" | "regex" | "json_shape" | "contains";
    field?: string;
    pattern: string;
  };
  confidence_on_match: "low" | "medium" | "high";
  requires_correlated_signal: boolean;
  false_positive_notes?: string[];
};

type BackendHintFinding = {
  id: string;
  scan_target_id: ScanTarget["id"];
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  backend_family:
    | "nodejs"
    | "python"
    | "java"
    | "dotnet"
    | "php"
    | "ruby"
    | "go"
    | "generic_api"
    | "unknown";
  technology: string;
  role:
    | "application_framework"
    | "runtime"
    | "reverse_proxy_or_web_server"
    | "api_style"
    | "session_layer"
    | "unknown";
  evidence_ids: Evidence["id"][];
  signature_ids: BackendHintSignature["id"][];
  matched_fields: Array<{
    evidence_id: Evidence["id"];
    url: string;
    method: "GET" | "HEAD" | "OPTIONS";
    field: string;
    redacted_value: string;
    match_reason: string;
  }>;
  negative_evidence_ids?: Evidence["id"][];
  conflict_notes?: string[];
  first_seen_at: string;
  last_seen_at: string;
};
```

Persistence rules:

* Store one `BackendHintFinding` per `(scan_target_id, technology, role)`.
* Append new evidence IDs when a later run supports the same finding.
* Do not duplicate findings for the same technology and role.
* Update `last_seen_at` on every supporting run.
* Keep `first_seen_at` stable.
* Store rejected or stale findings only when they replace a previously stored candidate or confirmed finding.
* Store negative evidence when a known explicit signature was checked and absent, but only if `persist_negative_evidence=true`.
* Redact cookie values, tokens, request IDs, session IDs, and stack trace paths before storing `matched_fields.redacted_value`.

Example finding:

```json
{
  "id": "backend-hint-01JEXAMPLE",
  "scan_target_id": "target-uuid",
  "status": "confirmed",
  "confidence": "high",
  "backend_family": "nodejs",
  "technology": "Express",
  "role": "application_framework",
  "evidence_ids": ["evidence-homepage-headers"],
  "signature_ids": ["sig-header-x-powered-by-express"],
  "matched_fields": [
    {
      "evidence_id": "evidence-homepage-headers",
      "url": "https://example.test/",
      "method": "GET",
      "field": "response.headers.x-powered-by",
      "redacted_value": "Express",
      "match_reason": "Explicit X-Powered-By header names Express"
    }
  ],
  "first_seen_at": "2026-05-18T21:00:00Z",
  "last_seen_at": "2026-05-18T21:00:00Z"
}
```

## Safety

This runner is read-only.

Allowed methods:

* `GET`
* `HEAD`
* `OPTIONS`, only when `allow_options_probe=true`

Disallowed behavior:

* No `POST`, `PUT`, `PATCH`, or `DELETE`.
* No login attempts.
* No credential spraying.
* No brute-force path discovery.
* No access to sensitive diagnostic paths by default.
* No payload injection.
* No exploit checks.
* No file upload.
* No form submission.
* No state-changing requests.
* No following links found in hostile evidence except the fixed probe plan above.

Payload restrictions:

* Query strings must be empty unless the base target URL already contains one.
* The random 404 path must contain only safe URL path characters.
* Do not include backend-specific exploit strings.
* Do not include framework debug trigger parameters.

PII and sensitive data handling:

* Do not store full cookie values.
* Do not store full stack traces by default.
* Do not store full response bodies in findings.
* Store snippets only through shared `Evidence` rules.
* Redact obvious secrets before persisting match fields.

AI involvement:

* `None`.
* No LLM is needed for this runner. All matching is deterministic.
* If future signatures need interpretation, add a separate Safety note naming the deterministic gap before enabling AI. Scanned content must remain untrusted evidence, consistent with the project’s LLM safety rule. 

## Pass/fail check

A run passes when all assertions below hold.

Positive assertions:

* Given a response with `X-Powered-By: Express`, the runner creates an Express backend finding with:

  * `technology="Express"`
  * `backend_family="nodejs"`
  * `role="application_framework"`
  * `confidence="high"`
  * `status="confirmed"`
  * at least one linked `Evidence` ID
* Given a response with `laravel_session`, the runner creates a Laravel finding with high confidence.
* Given a Spring Boot Whitelabel Error Page on the random 404 path, the runner creates a Spring Boot finding with high confidence.
* Given a JSON error body shaped like Spring Boot’s default error envelope, the runner creates a Spring Boot candidate or confirmed finding based on correlated evidence.
* Given only `Server: nginx`, the runner records nginx only as `reverse_proxy_or_web_server`, not as the application framework.
* Given `Server: nginx` plus `csrftoken` and Django CSRF evidence, the runner records separate nginx and Django findings.
* Given two weak independent hints for the same backend, the runner may raise confidence from low to medium.
* Given newer evidence that disproves an older candidate, the older finding becomes `rejected` or `stale`.

Negative assertions:

* The runner must not hard-code hostname to expected technology.
* The runner must not claim Django from `Server: nginx`.
* The runner must not claim Laravel from `X-Powered-By: PHP` alone.
* The runner must not claim Express from a JavaScript frontend bundle alone.
* The runner must not mark a low-confidence single weak signal as `confirmed`.
* The runner must not request `/admin`, `/wp-admin`, `/actuator`, `/debug`, `/phpinfo.php`, `/server-status`, or `/console`.
* The runner must not send `POST`, `PUT`, `PATCH`, or `DELETE`.
* The runner must not submit forms.
* The runner must not use credentials unless the scan context already provides them and RoE allows authenticated read-only testing.
* The runner must not store raw session cookie values.
* The runner must not store full stack traces in `matched_fields`.
* The runner must not call an LLM.
* The runner must not fail the whole scan because one optional diagnostic path times out.

## Test fixtures

Use these fixtures:

### `juice-shop`

Expected useful signals:

* Node.js / Express hints from headers, cookies, error behavior, API routes, or JSON error shape.
* API-style backend hints from `/api` or existing discovered API evidence.

Do not hard-code Juice Shop as Express. The test fixture must assert detection from captured response evidence.

### `dvwa`

Expected useful signals:

* PHP runtime hints.
* PHP session behavior.
* Possible Apache/nginx reverse proxy hints depending on container setup.

Do not claim Laravel, Symfony, or WordPress unless the evidence explicitly supports it.

### `webgoat`

Expected useful signals:

* Java / Spring-style hints.
* `JSESSIONID` or Java session behavior.
* Spring Boot style error responses if exposed.

Do not probe actuator endpoints in this spec.

### Fixture requirements

Each fixture test should include:

* saved HTTP response evidence for deterministic unit tests
* one integration test against the container fixture, if the project already supports container fixture runs
* one negative test where misleading headers are present
* one conflict test with proxy header plus app framework body/cookie evidence
* one stale-finding update test

Suggested saved fixture files:

* `tests/fixtures/backend_hints/express_homepage_response.json`
* `tests/fixtures/backend_hints/django_csrf_response.json`
* `tests/fixtures/backend_hints/spring_boot_404_response.json`
* `tests/fixtures/backend_hints/php_session_response.json`
* `tests/fixtures/backend_hints/nginx_proxy_django_app_response.json`
* `tests/fixtures/backend_hints/misleading_header_negative_response.json`

## Acceptance criteria

The implementation is accepted when:

* The runner is idempotent for the same target and evidence set.
* The runner completes within the configured request budget.
* Default run sends no more than `8` new requests per target.
* Existing evidence is reused before new requests are sent.
* Every finding links to at least one shared `Evidence` record.
* Every finding has `confidence` set to `low`, `medium`, or `high`.
* Every finding has `status` set to `candidate`, `confirmed`, `rejected`, or `stale`.
* Findings distinguish app framework, runtime, reverse proxy/web server, API style, and session layer.
* Conflicting hints are stored as separate findings with conflict notes.
* TLS errors, DNS errors, refused connections, malformed responses, and timeouts are handled as non-fatal scan observations.
* Optional diagnostic path failures do not stop the runner.
* Cookie values and sensitive headers are redacted before persistence.
* No raw credentials, tokens, or session values are logged.
* No mutating HTTP methods are used.
* No disallowed diagnostic paths are probed.
* Tests cover positive detection, weak-signal confidence, conflicting evidence, negative assertions, stale/rejected updates, TLS failure handling, timeout handling, and redaction.
* The runner does not use AI.

