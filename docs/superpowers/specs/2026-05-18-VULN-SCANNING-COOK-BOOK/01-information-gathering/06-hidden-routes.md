---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 6
slug: hidden-routes
status: done        # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.6 Hidden routes

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

Detect application routes that are not directly visible from the landing page but are exposed through crawlable metadata, client-side bundles, predictable framework files, redirects, or low-volume path probing. A runner cares because hidden routes often expose admin panels, debug pages, API explorers, staging leftovers, backup files, or unauthenticated endpoints that shape later scan phases.

## Inputs

The runner receives a shared `ScanTarget` and uses its `base_url`, `host`, and optional resolved IP metadata.

Optional inputs:

* `credentials_ref`: reference to credentials managed outside this stub. The stub must not store raw credentials.
* `use_authenticated_session`: default `false`; only allowed when RoE permits authenticated testing.
* `max_requests`: default `80`.
* `max_depth`: default `2`.
* `request_timeout_ms`: default `8000`.
* `follow_redirects`: default `true`, capped to same-origin redirects unless RoE allows otherwise.
* `allowed_methods`: default `["GET", "HEAD"]`.
* `same_origin_only`: default `true`.
* `include_common_paths`: default `true`.
* `include_js_route_extraction`: default `true`.
* `include_metadata_files`: default `true`.
* `include_api_hints`: default `true`.
* `path_wordlist_ref`: optional reference to a small built-in path list.
* `exclude_paths`: optional path prefixes to skip.
* `respect_robots_txt`: default `true` for discovery hints, but `Disallow` paths may still be recorded as route hints without being fetched if policy requires that.
* `record_negative_evidence`: default `true`, used to prove skipped or missing routes during tests.
* `user_agent`: scanner default user agent.

The runner must normalize `base_url` before use:

* Preserve scheme and host.
* Remove fragments.
* Preserve an explicit non-default port.
* Ensure path probing starts from the origin root, not from an arbitrary deep URL, unless the target path is intentionally scoped.

## Detection logic

Detection is deterministic. Do not ask an LLM to infer hidden routes.

### 1. Establish baseline

Send a `GET` request to `/` or the normalized target path.

Record shared `Evidence` for:

* final URL after redirect
* status code
* response headers
* content type
* body hash
* body snippet or capped body reference
* redirect chain
* fetch error, if any

The baseline response is used to:

* identify same-origin links
* identify script and asset URLs
* identify framework-specific route hints
* build a soft 404 profile

### 2. Build a soft 404 profile

Probe 2 random, high-entropy paths using `GET`:

* `/.well-known/scanner-nonexistent-<random>`
* `/scanner-nonexistent-<random>`

Record their status, body hash, title, content length, and selected text fingerprint.

A response is treated as soft 404 when one or more of these are true:

* status is `404` or `410`
* status is `200` but body fingerprint matches both random missing paths
* title or body contains common not-found language and content length is close to random missing paths
* redirect target is a known not-found route

The runner must not mark a discovered route as confirmed only because it returns `200`. Compare it against the soft 404 profile.

### 3. Collect passive route candidates

Parse the baseline HTML and same-origin linked assets within request budget.

Extract route candidates from:

* `<a href>`
* `<form action>`
* `<script src>`
* `<link href>`
* `<iframe src>`
* inline JavaScript strings that look like same-origin paths
* external JavaScript bundles from same origin
* source map references, but do not fetch source maps unless allowed by config
* `robots.txt`
* `sitemap.xml`
* `sitemap_index.xml`
* `security.txt`
* `/.well-known/security.txt`
* common OpenAPI descriptors:

  * `/openapi.json`
  * `/swagger.json`
  * `/api-docs`
  * `/swagger-ui/`
  * `/docs`
  * `/redoc`
* common app metadata:

  * `/manifest.json`
  * `/asset-manifest.json`
  * `/build/asset-manifest.json`
  * `/static/js/`
  * `/favicon.ico` only as a supporting fingerprint, not as a hidden route

Do not fetch off-origin URLs unless the shared scanner scope allows it.

### 4. Extract client-side route patterns

When `include_js_route_extraction=true`, fetch same-origin JavaScript assets linked from baseline HTML.

Extract candidate paths using deterministic regex patterns only.

Examples:

```regex
["'`](/(?:admin|api|debug|docs|swagger|graphql|login|register|reset|user|users|account|profile|settings|internal|manage|management|actuator|health|metrics|version|config|backup|uploads|files|assets)[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)["'`]
```

```regex
path\s*:\s*["'`](/[^"'`]+)["'`]
```

```regex
route\s*:\s*["'`](/[^"'`]+)["'`]
```

```regex
url\s*:\s*["'`](/api/[^"'`]+)["'`]
```

Normalize candidates:

* strip quotes
* remove fragments
* preserve query strings only when they are part of a static route hint
* reject `javascript:`, `data:`, `mailto:`, `tel:`, and absolute off-origin URLs
* collapse duplicate slashes in path only
* remove obvious build chunk filenames unless they represent fetchable routes
* cap candidate length to a sane maximum, such as 300 characters
* reject paths containing whitespace control characters

### 5. Add small common-path probes

When `include_common_paths=true`, add a small built-in path set.

The first version should stay conservative. Suggested paths:

```text
/admin
/admin/
/administrator
/login
/logout
/register
/signup
/account
/profile
/settings
/dashboard
/api
/api/
/api/v1
/graphql
/graphiql
/playground
/swagger
/swagger/
/swagger-ui/
/swagger-ui/index.html
/openapi.json
/swagger.json
/api-docs
/docs
/redoc
/health
/healthz
/status
/metrics
/version
/debug
/debug/
/actuator
/actuator/health
/actuator/env
/server-status
/phpinfo.php
/.env
/config
/config.json
/backup
/backups
/uploads
/files
```

Risky or noisy names must be gated behind config and RoE. The default list must not contain large brute-force dictionaries.

### 6. Rank candidates before fetching

Each candidate receives a deterministic priority score.

Higher priority:

* discovered in `robots.txt`
* discovered in `sitemap.xml`
* discovered in same-origin JavaScript
* discovered in forms
* path suggests API, admin, debug, docs, health, metrics, config, backup, upload, auth, or account
* path has not already been fetched
* path is near the target root

Lower priority:

* static assets
* images, fonts, CSS files
* duplicated route with only fragment change
* very long query strings
* paths likely generated by frontend router state only
* paths matching `exclude_paths`

Fetch candidates in priority order until `max_requests` is reached.

### 7. Confirm routes

For each candidate, use `GET` by default. Use `HEAD` only when configured and only as a request-saving optimization. If `HEAD` gives a useful positive signal, confirm with `GET` unless config forbids body fetches.

A route is a candidate finding when:

* it is same-origin and in scope
* it returns a status that differs from the soft 404 profile
* or it redirects to a meaningful same-origin route
* or it returns authentication/authorization status such as `401`, `403`, or app-specific login redirect
* or it returns structured API metadata
* or it returns a directory listing
* or it exposes debug, metrics, version, config, backup, upload, API, documentation, or admin indicators

A route is confirmed when at least one positive signal exists:

* status `200`, `204`, `206`, `301`, `302`, `307`, `308`, `401`, or `403` and not soft 404
* response content type and body are consistent with a real route
* response body title/header differs from baseline and soft 404
* response contains route-specific markers
* response is an API response, OpenAPI schema, GraphQL response, admin page, login page, health endpoint, metrics page, or directory listing
* redirect target is same-origin and meaningful
* response has auth boundary evidence, such as `WWW-Authenticate`, login form, session redirect, or access denied page

A route is rejected when:

* it matches the soft 404 profile
* it is off-origin and out of scope
* it is excluded by config
* it exceeds URL length or path safety limits
* it requires a method outside `GET`/`HEAD`
* it fails consistently due to network error and no route evidence exists

A route is stale when:

* it was previously confirmed but now matches soft 404
* it was previously confirmed but now returns a stable transport error for the current scan
* it was previously confirmed under authenticated mode but is not observable in unauthenticated mode and no current authenticated evidence exists

### 8. Classify route type

Assign zero or more route tags from deterministic evidence:

* `admin`
* `auth`
* `api`
* `graphql`
* `docs`
* `debug`
* `health`
* `metrics`
* `version`
* `config`
* `backup`
* `upload`
* `directory_listing`
* `static_asset`
* `frontend_route`
* `well_known`
* `sitemap`
* `robots`
* `unknown`

Use evidence, not hostname assumptions.

### 9. Confidence rules

Use `high` confidence when:

* route is fetched successfully and differs from soft 404
* and response has route-specific status, headers, body, or redirect evidence

Use `medium` confidence when:

* route appears in trusted site metadata such as sitemap or robots
* or route appears in same-origin JavaScript and fetch returns auth boundary or redirect evidence
* but response body is too small or ambiguous

Use `low` confidence when:

* route is extracted from JavaScript but not fetched due to budget
* route is hinted only by source map comment or inline string
* response is ambiguous and close to soft 404
* evidence is incomplete

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Persist one `Evidence` record per fetched route or important route source:

* baseline response
* random soft 404 probes
* `robots.txt`
* sitemap files
* JavaScript assets used for extraction
* each route confirmation response
* skipped candidate summary, when useful for audit

### `HiddenRouteSignature`

A signature is a deterministic rule or source that produced a route candidate.

```json
{
  "id": "string",
  "scan_target_id": "uuid",
  "source_evidence_id": "uuid",
  "source_type": "baseline_html | robots_txt | sitemap | javascript | common_path | openapi_hint | well_known | redirect | form | prior_memory",
  "candidate_path": "/admin",
  "candidate_url": "https://example.test/admin",
  "extraction_method": "html_href | html_form_action | js_regex_path | robots_disallow | sitemap_loc | builtin_wordlist | redirect_location",
  "matched_pattern": "string | null",
  "priority": 0,
  "same_origin": true,
  "in_scope": true,
  "normalized": true,
  "created_at": "ISO-8601"
}
```

Field notes:

* `id` should be stable for the same scan target, source type, candidate path, and extraction method.
* `source_evidence_id` points to the shared `Evidence` that produced the candidate.
* `matched_pattern` must not contain full sensitive payloads. Store only the route pattern or short matched token.
* `priority` is deterministic and used for request-budget ordering.

### `HiddenRouteFinding`

A finding represents the current state of one discovered route.

```json
{
  "id": "string",
  "scan_target_id": "uuid",
  "route_url": "https://example.test/admin",
  "route_path": "/admin",
  "method": "GET",
  "status": "candidate | confirmed | rejected | stale",
  "confidence": "low | medium | high",
  "route_tags": ["admin", "auth"],
  "source_signature_ids": ["string"],
  "evidence_ids": ["uuid"],
  "http_status": 403,
  "content_type": "text/html",
  "content_length": 1234,
  "body_hash": "sha256:...",
  "redirect_chain": [
    {
      "status": 302,
      "location": "/login"
    }
  ],
  "auth_boundary_detected": true,
  "soft_404_match": false,
  "directory_listing_detected": false,
  "sensitive_route_hint": true,
  "title": "Admin",
  "summary": "Hidden admin route discovered from same-origin JavaScript and confirmed by 403 response.",
  "first_seen_at": "ISO-8601",
  "last_seen_at": "ISO-8601",
  "stale_reason": "string | null"
}
```

Persistence rules:

* Deduplicate by `(scan_target_id, route_path, method)`.
* Update `last_seen_at` on every scan where the route is still observed.
* Preserve `first_seen_at`.
* Add new evidence IDs rather than overwriting previous evidence.
* If a route changes from confirmed to soft 404, mark `stale` and store the new negative evidence.
* If a route changes from rejected to confirmed, keep prior negative evidence and update status to `confirmed`.
* Do not persist raw credentials, cookies, tokens, or full sensitive response bodies in `HiddenRouteFinding`.

## Safety

Default behavior is read-only.

Allowed methods:

* `GET`
* `HEAD`

Disallowed by default:

* `POST`
* `PUT`
* `PATCH`
* `DELETE`
* unsafe WebDAV methods
* GraphQL mutations
* form submission
* login attempts
* brute-force path enumeration
* recursive crawling beyond configured depth
* fetching off-origin URLs
* fetching unbounded source maps
* downloading large files
* following redirects to external domains
* executing JavaScript
* executing scripts found in pages
* using discovered credentials or tokens
* writing to any target endpoint

Payload restrictions:

* Do not send attack payloads.
* Do not send SQL, XSS, command injection, template injection, or traversal payloads.
* Do not fuzz path parameters.
* Do not mutate query strings beyond requesting discovered static URLs.
* Do not probe backup filename permutations beyond the small allowed path list.
* Do not add custom auth headers unless `use_authenticated_session=true` and RoE allows it.

Request discipline:

* Enforce `max_requests`.
* Enforce per-host rate limits from the shared runner.
* Enforce timeout.
* Same-origin only by default.
* Skip paths matching `exclude_paths`.
* Skip very large downloads based on `Content-Type` and `Content-Length` when known.
* Treat `robots.txt` as a route source. Fetching disallowed paths must follow product policy and RoE.

PII and sensitive data handling:

* Redact obvious secrets before logs.
* Do not store full response bodies in logs.
* Store capped snippets only through shared `Evidence`.
* If a hidden route exposes user data, record the route and minimal proof, then stop deeper content inspection.
* Never persist cookies, bearer tokens, basic auth values, CSRF tokens, or session IDs in route findings.

AI involvement:

* `None` for route discovery, extraction, ranking, confirmation, and persistence.
* A future AI summarizer may be used only after deterministic findings exist, and only for report prose from validated findings. It must not affect status, confidence, route tags, or severity.
* If JavaScript route extraction misses framework-specific dynamic routes, add deterministic extractors first. Do not use AI as the default parser.

## Pass/fail check

The implementation passes when all positive and negative assertions below hold.

### Positive assertions

* Given a target with `/robots.txt` containing `Disallow: /admin`, the runner creates a `HiddenRouteSignature` with `source_type="robots_txt"` and `candidate_path="/admin"`.
* If `/admin` returns `200`, `401`, `403`, or a meaningful same-origin redirect that does not match soft 404, the runner creates or updates a `HiddenRouteFinding`.
* If a same-origin JavaScript bundle contains `"/api/users"` as a route-like string, the runner extracts `/api/users` as a candidate when JavaScript extraction is enabled.
* If `/api/users` returns `401` or `403`, the route is marked `confirmed` with `auth_boundary_detected=true`.
* If `/swagger.json` returns valid JSON with OpenAPI-like fields, the route is tagged `api` and `docs` or `openapi` if the shared tag set supports it.
* If `/graphql` returns a GraphQL-specific error or landing response to `GET`, the route is tagged `graphql`.
* If `/health` returns a non-soft-404 health response, the route is marked `confirmed`.
* If a route is discovered from sitemap and fetched successfully, `source_signature_ids` links back to the sitemap signature.
* If a route is found by multiple sources, the runner deduplicates it into one `HiddenRouteFinding` and appends all signature IDs.
* If a previously confirmed route now returns soft 404, the runner marks it `stale` and stores the negative evidence.
* The runner records baseline and soft 404 evidence before confirming routes.
* Confidence is `high` only when fetch evidence confirms the route.
* Confidence is `low` when a candidate was extracted but not fetched due to budget.

### Negative assertions

* The runner must not mark a route `confirmed` only because it returned `200`; it must compare against the soft 404 profile.
* The runner must not fetch off-origin URLs by default.
* The runner must not execute JavaScript.
* The runner must not submit forms.
* The runner must not use methods other than `GET` or `HEAD`.
* The runner must not mutate application state.
* The runner must not perform large wordlist brute forcing.
* The runner must not ignore `max_requests`.
* The runner must not store raw cookies, bearer tokens, credentials, or CSRF tokens in findings.
* The runner must not hard-code hostnames or fixture-specific expected routes.
* The runner must not call an LLM for route extraction, status, confidence, or tagging.
* The runner must not follow external redirects unless explicitly allowed by shared scope policy.
* The runner must not treat static assets such as `/favicon.ico` as hidden-route findings unless they reveal a distinct route source or framework hint.
* The runner must not classify a route as `admin`, `debug`, `api`, or similar without path, header, status, redirect, or body evidence.

## Test fixtures

Primary fixture: `juice-shop`.

Recommended fixture behavior:

* `juice-shop` exposes client-side route hints in JavaScript bundles.
* The runner should discover routes such as admin, login, account, API, or score-board style frontend paths from same-origin HTML/JS evidence.
* The exact expected routes must be derived from fixture responses during the test setup, not hard-coded by hostname.

Secondary fixture: `webgoat`.

Use for Java/Spring-like path behavior if available:

* `/actuator`
* `/actuator/health`
* login/auth redirects
* documentation or API hints when present

Optional new fixture slug: `hidden-routes-lab`.

A small deterministic container can expose:

* `/` with one visible link only
* `/robots.txt` with `Disallow: /admin`
* `/sitemap.xml` with `/docs` and `/api/status`
* `/static/app.js` containing string routes:

  * `/admin`
  * `/api/users`
  * `/debug/config`
  * `/graphql`
* `/admin` returning `403`
* `/api/users` returning `401`
* `/debug/config` returning `403` or sanitized config placeholder
* `/graphql` returning GraphQL-style `GET` error
* `/missing-*` returning a soft 404 `200` page
* `/fake` returning the same soft 404 page as random missing paths

The fixture must prove:

* route extraction from metadata
* route extraction from JavaScript
* soft 404 rejection
* auth boundary confirmation
* deduplication across multiple sources
* stale transition when a route is removed between fixture modes

## Acceptance criteria

* The scanner is idempotent: repeated runs against the same unchanged target do not create duplicate findings.
* The scanner completes within the configured request budget.
* The scanner respects `max_requests`, `max_depth`, timeout, same-origin scope, and excluded paths.
* The scanner handles TLS errors, connection resets, malformed redirects, invalid content encodings, and oversized bodies gracefully.
* The scanner stores enough shared `Evidence` to explain every confirmed, rejected, and stale route decision.
* The scanner never relies on hostname-specific assumptions.
* The scanner uses deterministic extraction, ranking, confirmation, tagging, confidence, and stale logic.
* The scanner does not use AI for this stub.
* The scanner avoids noisy brute-force behavior.
* The scanner does not perform mutating requests.
* The scanner does not leak secrets into logs or findings.
* Unit tests cover URL normalization, HTML extraction, JavaScript extraction, robots parsing, sitemap parsing, common-path probing, soft 404 handling, deduplication, confidence, stale updates, and safety gates.
* Integration tests pass against at least one fixture with hidden routes exposed through both metadata and JavaScript.
* Failures are explicit: network errors, skipped paths, budget exhaustion, and soft 404 rejection are visible in evidence or runner diagnostics.
* No flaky retries: retries are capped and only used for transport-level failures that are safe to repeat.

