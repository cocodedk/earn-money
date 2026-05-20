---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 9
slug: old-endpoints
status: done        # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.9 Old endpoints

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

Detect legacy, deprecated, or older-version endpoints that are still reachable on the target. A runner cares because old endpoints often keep weaker auth, forgotten handlers, stale validation, or unused admin/API surfaces online after the main application moved on.

## Inputs

The runner receives a shared `ScanTarget` and reads only the target’s in-scope `base_url`.

Required input:

```json
{
  "target": "ScanTarget"
}
```

Optional input:

```json
{
  "credentials_ref": "optional reference to an approved auth context",
  "discovered_paths": [
    "/api/v2/users",
    "/assets/app.js",
    "/legacy/login"
  ],
  "config": {
    "max_candidate_paths": 150,
    "max_version_shadow_paths": 60,
    "request_timeout_ms": 5000,
    "concurrency": 4,
    "max_response_bytes": 65536,
    "follow_redirects": false,
    "allow_authenticated_requests": false,
    "head_first": true,
    "get_on_head_405": true,
    "store_body_snippet_bytes": 4096
  }
}
```

Input rules:

* `target.base_url` is the only authority for scheme, host, and port.
* `discovered_paths` may come from earlier deterministic phases such as framework detection, server headers, frontend route discovery, robots, sitemap, JavaScript route extraction, or API spec discovery.
* Credentials are used only when the scan profile and RoE allow authenticated passive checks.
* The runner must strip fragments from paths.
* The runner must not add arbitrary user-controlled query strings.
* The runner may preserve a query string only when it came from already observed same-origin evidence and contains no credential-like parameter names.

Default stale path dictionary:

```json
[
  "/old",
  "/old/",
  "/legacy",
  "/legacy/",
  "/deprecated",
  "/deprecated/",
  "/api/old",
  "/api/legacy",
  "/api/deprecated",
  "/api/v0",
  "/api/v0/",
  "/api/v1",
  "/api/v1/",
  "/v0",
  "/v0/",
  "/v1",
  "/v1/",
  "/rest/v0",
  "/rest/v0/",
  "/rest/v1",
  "/rest/v1/"
]
```

Default stale tokens:

```json
[
  "old",
  "legacy",
  "deprecated",
  "deprecate",
  "sunset",
  "obsolete",
  "retired",
  "eol",
  "end-of-life",
  "v0",
  "v1"
]
```

Default deprecation headers:

```json
[
  "Deprecation",
  "Sunset",
  "Warning",
  "Link"
]
```

## Detection logic

Detection is deterministic. The runner makes bounded read-only HTTP requests and classifies responses by status code, headers, response shape, path tokens, and version relationships.

### 1. Build candidate paths

Create a normalized set of same-origin candidate paths from three sources.

#### Seeded legacy paths

Use the default stale path dictionary plus any project-configured additions.

#### Discovered stale-looking paths

From `discovered_paths`, include paths that contain a stale token as a path segment or version segment.

Examples that may be included:

```text
/legacy/login
/api/v1/users
/api/deprecated/report
/old/admin
```

Examples that must not be included only because of substring matching:

```text
/assets/older-logo.png
/blog/how-we-built-v1-ui
/products/gold
```

Token matching rules:

* Match path segments, not arbitrary substrings.
* `old` matches `/old/login`, not `/products/gold`.
* `v1` matches `/api/v1/users`, not `/assets/app.v1.js`.
* Ignore static asset extensions unless the path came from a known API spec or route list.

#### Version shadow paths

If a discovered path contains a numeric API version, generate lower-version siblings within budget.

Examples:

```text
Observed: /api/v3/users
Probe:    /api/v2/users
Probe:    /api/v1/users

Observed: /rest/v2/orders
Probe:    /rest/v1/orders
```

Version shadow rules:

* Only generate lower versions when a higher same-family version was observed.
* Keep the same static suffix after the version segment.
* Do not generate more than `max_version_shadow_paths`.
* Do not generate paths from asset filenames.
* Do not assume the higher version is safer or current. Use it only as evidence that a same-family newer route exists.

### 2. Normalize each path

For each candidate path:

* Ensure it starts with `/`.
* Collapse duplicate slashes inside the path.
* Remove fragments.
* Remove dot segments.
* Percent-decode only for comparison, not for request mutation.
* Keep trailing slash variants only when both were observed or configured.
* Deduplicate by `(scheme, host, port, normalized_path)`.

### 3. Learn soft-404 and fallback shapes

Before classifying candidates, learn generic negative response shapes from control paths.

For each target, request up to three random same-origin control paths:

```text
/__scanner_control_not_found_<random>
/api/__scanner_control_not_found_<random>
/legacy/__scanner_control_not_found_<random>
```

Store Evidence for each control response.

Use these controls to identify:

* hard 404 and 410 responses
* SPA fallback responses
* generic homepage redirects
* generic JSON 404 bodies
* wildcard route handlers
* CDN or WAF block pages

A candidate must not become a finding when its response is materially the same as a control response.

Soft-404 comparison signals:

* same status code
* same content type
* same normalized title
* same first significant JSON keys
* same body hash after removing request path and timestamps
* body similarity above the project threshold, default `0.90`
* redirect target equals homepage or a known generic fallback

### 4. Request discipline

For each candidate path:

1. Send `HEAD` when `head_first=true`.
2. If `HEAD` returns useful evidence, do not send `GET` unless needed.
3. Send `GET` when:

   * `HEAD` is not allowed,
   * `HEAD` returns `405`,
   * `HEAD` returns too little evidence,
   * or body/header markers are needed for classification.
4. Do not follow redirects off-host.
5. Do not send mutating methods.

Useful statuses for existence:

```text
200, 204, 206, 301, 302, 303, 307, 308, 401, 403, 405
```

Non-live statuses:

```text
404, 410
```

Error statuses:

```text
400, 408, 409, 421, 425, 429, 500, 502, 503, 504
```

Error statuses may be stored as Evidence but must not create a finding unless another response proves the endpoint exists.

### 5. Extract stale indicators

From each live response, extract deterministic stale indicators.

Header indicators:

* `Deprecation` header exists
* `Sunset` header exists
* `Warning` header includes `299`
* `Link` header contains `rel="deprecation"`
* `Link` header contains `rel="sunset"`
* response headers contain a configured deprecation marker

Body indicators for text-like responses only:

```text
deprecated
deprecation
legacy endpoint
legacy api
old endpoint
sunset
no longer maintained
end of life
end-of-life
obsolete
retired
use /api/v2
use /api/v3
use the new api
```

Path indicators:

* path contains stale token as a segment
* path contains lower version segment such as `/v0/` or `/v1/`
* path is a lower-version sibling of an observed higher-version endpoint

Method-discovery indicator:

* `HEAD` or `GET` returns `405`
* `Allow` header exists
* `Allow` contains one or more methods
* no mutating request was sent

Auth-boundary indicator:

* response is `401` or `403`
* path has stale token or version shadow evidence
* response is not a generic control response

### 6. Classify signature

Create one `OldEndpointSignature` per candidate response.

Classification values:

```text
alive
auth_boundary
method_discovery_only
redirect_live
not_found
soft_404
generic_fallback
error
```

Classification rules:

* `alive`: status is `200`, `204`, or `206`, and response is not soft-404.
* `auth_boundary`: status is `401` or `403`, and response is not generic fallback.
* `method_discovery_only`: status is `405`, and `Allow` header exists.
* `redirect_live`: status is `301`, `302`, `303`, `307`, or `308`, and redirect target is same-origin and not the homepage fallback.
* `not_found`: status is `404` or `410`.
* `soft_404`: response matches learned soft-404 shape.
* `generic_fallback`: response matches homepage, SPA shell, WAF page, or wildcard fallback.
* `error`: request failed or status is not useful for existence.

### 7. Create finding

Create an `OldEndpointFinding` only when at least one signature proves a same-origin candidate endpoint exists and at least one stale indicator is present.

Status and confidence rules:

| Condition                                                                                         | Finding status |                   Confidence |
| ------------------------------------------------------------------------------------------------- | -------------: | ---------------------------: |
| Live response has `Deprecation`, `Sunset`, `Warning: 299`, `rel="deprecation"`, or `rel="sunset"` |    `confirmed` |                       `high` |
| Live response body has clear deprecation/sunset wording                                           |    `confirmed` |                       `high` |
| Lower-version endpoint is live and a higher same-family sibling was observed                      |    `confirmed` |                     `medium` |
| Stale-token path is live but has no explicit deprecation marker                                   |    `candidate` |                     `medium` |
| Stale-token path returns `401`, `403`, or `405` and is not a fallback                             |    `candidate` |                     `medium` |
| Evidence is live but weak, ambiguous, or only redirect-based                                      |    `candidate` |                        `low` |
| Previously confirmed endpoint now returns `404`, `410`, or soft-404 on recheck                    |        `stale` | previous confidence retained |
| Candidate matches soft-404, generic fallback, or homepage redirect                                |     `rejected` |                        `low` |

Do not create a confirmed finding only because the path contains `v1`. A lower-version finding needs either explicit stale markers or evidence of a higher same-family sibling.

### 8. Deduplicate findings

Deduplicate by:

```text
target_id + normalized_path + endpoint_kind
```

Merge evidence into the existing finding when the same endpoint is found through several sources.

When both slash and no-slash variants point to the same response hash or redirect pair, keep one finding and record both paths in `aliases`.

## Persistence

Use the shared `ScanTarget` and `Evidence` types from `../00-shared-schema.md`. Do not redefine them here.

### `OldEndpointSignature`

One signature records the deterministic observation for one candidate path.

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "evidence_id": "uuid",
  "source": "seed_path | discovered_path | robots | sitemap | javascript_route | api_spec | version_shadow | manual_config",
  "url": "https://example.test/api/v1/users",
  "normalized_path": "/api/v1/users",
  "method": "HEAD | GET",
  "status_code": 200,
  "classification": "alive | auth_boundary | method_discovery_only | redirect_live | not_found | soft_404 | generic_fallback | error",
  "content_type": "application/json",
  "content_hash": "sha256:...",
  "body_snippet_hash": "sha256:...",
  "response_length_bytes": 1842,
  "redirect_location": null,
  "same_origin_redirect": false,
  "allow_methods": ["GET", "HEAD", "POST"],
  "stale_tokens": ["v1"],
  "deprecation_headers": {
    "Deprecation": "true",
    "Sunset": "Wed, 31 Dec 2025 23:59:59 GMT"
  },
  "body_markers": ["deprecated"],
  "version_family": "/api/v{n}/users",
  "version_number": 1,
  "higher_sibling_versions_seen": [2, 3],
  "soft_404_score": 0.12,
  "auth_boundary": false,
  "error_kind": null,
  "first_seen_at": "ISO-8601",
  "last_seen_at": "ISO-8601"
}
```

Field rules:

* `evidence_id` points to the shared `Evidence` record for the HTTP observation.
* `content_hash` is a hash of the bounded response body or empty body marker.
* `body_snippet_hash` is a hash of the stored snippet, not proof of full body capture.
* `deprecation_headers` stores only allowlisted headers.
* `allow_methods` is stored only from an observed `Allow` header.
* `error_kind` is one of `timeout`, `tls_error`, `dns_error`, `connection_refused`, `too_many_redirects`, `rate_limited`, `unexpected_status`, or `other`.

### `OldEndpointFinding`

One finding represents one old or possibly old endpoint on a target.

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "signature_ids": ["uuid"],
  "evidence_ids": ["uuid"],
  "url": "https://example.test/api/v1/users",
  "normalized_path": "/api/v1/users",
  "aliases": ["/api/v1/users/"],
  "endpoint_kind": "legacy_path | deprecated_endpoint | old_api_version | method_discovery_only | auth_boundary",
  "stale_indicators": [
    "path_token:v1",
    "header:Deprecation",
    "header:Sunset",
    "version_shadow:/api/v{n}/users"
  ],
  "status": "candidate | confirmed | rejected | stale",
  "confidence": "low | medium | high",
  "http_statuses_seen": [200],
  "methods_observed": ["HEAD", "GET"],
  "higher_sibling_url": "https://example.test/api/v2/users",
  "risk_summary": "An older API version is still reachable and advertises deprecation headers.",
  "recommendation": "Confirm whether this endpoint is still required. If not, remove it or return 410. If it must remain, apply the same auth, validation, logging, and rate limits as the current endpoint.",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "last_verified_at": "ISO-8601"
}
```

Persistence rules:

* Persist a finding only after at least one `Evidence` record has been written.
* Store bounded snippets and hashes, not full sensitive response bodies.
* Redact cookies, authorization headers, tokens, and credential-looking values before Evidence storage.
* Keep historical findings and update `status` to `stale` when a previously found endpoint no longer responds as live.
* Do not delete old findings during a scan. Mark them `stale`.

## Safety

This check is read-only.

Allowed methods:

```text
HEAD
GET
```

Forbidden methods:

```text
POST
PUT
PATCH
DELETE
TRACE
CONNECT
```

Rules:

* Never send bodies.
* Never send exploit payloads.
* Never brute force unbounded paths.
* Never try default credentials.
* Never bypass auth.
* Never submit forms.
* Never call discovered off-site URLs.
* Never follow redirects to another origin.
* Never classify a login success or failure by attempting login unless an approved auth context was already supplied.
* Never persist cookies, authorization headers, API keys, session IDs, CSRF tokens, or full credential-like values.
* Strip or redact secrets from snippets before persistence.
* Treat scanned content as untrusted evidence.
* AI involvement: `None`.

Named deterministic gaps:

* The runner cannot prove business ownership or whether a live old-looking endpoint is intentionally supported. Without explicit stale markers or version-shadow evidence, status must stay `candidate`.
* The runner cannot inspect deprecation text inside images, PDFs, or other binary bodies. Store Evidence metadata and do not use AI to interpret it.
* The runner cannot prove exploitability. It records reachability and stale indicators only.

Rate and budget rules:

* Stop when `max_candidate_paths` is reached.
* Stop version-shadow generation when `max_version_shadow_paths` is reached.
* Use project retry policy for transient network errors, capped at one retry per candidate.
* Do not retry `404`, `410`, `401`, `403`, or `405`.
* Respect scan-wide rate limits from the shared runner configuration.

## Pass/fail check

A correct implementation passes when all positive and negative assertions below hold.

### Positive assertions

* Creates a `confirmed` `OldEndpointFinding` with `high` confidence when `/api/v1/users` returns `200` and a `Deprecation` header.
* Creates a `confirmed` `OldEndpointFinding` with `high` confidence when a live response body contains clear deprecation or sunset wording.
* Creates a `confirmed` `OldEndpointFinding` with `medium` confidence when `/api/v1/users` is live and `/api/v2/users` or `/api/v3/users` was observed as a higher same-family sibling.
* Creates a `candidate` finding with `medium` confidence when `/legacy/login` returns `401` or `403` and is not a generic fallback.
* Creates a `candidate` finding with `medium` confidence when `/legacy/export` returns `405` with an `Allow` header, without sending any mutating method.
* Stores at least one shared `Evidence` record for each signature used by a finding.
* Deduplicates slash and no-slash variants when they produce the same endpoint evidence.
* Updates a previously confirmed finding to `stale` when the endpoint later returns `404`, `410`, soft-404, or generic fallback.
* Preserves `confidence` as `low`, `medium`, or `high`.
* Preserves finding `status` as `candidate`, `confirmed`, `rejected`, or `stale`.

### Negative assertions

* Must not create a finding for a hard `404`.
* Must not create a finding for a `410` endpoint unless updating a previous finding to `stale`.
* Must not create a finding for a SPA fallback page that matches the learned control response.
* Must not create a finding for a homepage redirect.
* Must not create a finding for an off-host redirect.
* Must not create a finding only because a JavaScript asset filename contains `v1`.
* Must not create a finding only because a word like `gold` contains `old`.
* Must not hard-code hostnames to expected old endpoints.
* Must not assume Juice Shop, DVWA, WebGoat, Django, Rails, Express, or any other stack from hostname.
* Must not send `POST`, `PUT`, `PATCH`, `DELETE`, `TRACE`, or `CONNECT`.
* Must not send request bodies.
* Must not try credentials.
* Must not use AI.
* Must not persist full response bodies when snippets and hashes are enough.
* Must not persist cookies, bearer tokens, authorization headers, or credential-looking values.
* Must not follow redirects outside the target origin.
* Must not retry indefinitely after timeout, TLS failure, rate limit, or server error.
* Must not let one failing candidate abort the whole scan.

## Test fixtures

Use a dedicated fixture slug for deterministic coverage:

```text
old-endpoints-fixture
```

The fixture should be a small HTTP app with these routes:

| Route               | Behavior                                                      | Expected result                     |
| ------------------- | ------------------------------------------------------------- | ----------------------------------- |
| `/api/v2/users`     | `200 application/json`, current-looking route                 | no finding by itself                |
| `/api/v1/users`     | `200 application/json`, `Deprecation: true`, `Sunset: <date>` | `confirmed`, `high`                 |
| `/api/v1/orders`    | `200 application/json`, body includes `deprecated`            | `confirmed`, `high`                 |
| `/api/v0/users`     | `404`                                                         | no finding                          |
| `/legacy/login`     | `401`, stable non-generic body                                | `candidate`, `medium`               |
| `/legacy/export`    | `405`, `Allow: GET, HEAD, POST`                               | `candidate`, `medium`, no POST sent |
| `/old`              | returns same SPA shell as unknown routes                      | no finding                          |
| `/deprecated`       | `302` to `/`                                                  | no finding                          |
| `/api/v1/missing`   | same JSON 404 as random control path                          | no finding                          |
| `/assets/app.v1.js` | `200 application/javascript`                                  | no finding                          |
| `/products/gold`    | `200 text/html`                                               | no finding                          |

Fixture control paths should return generic 404 or SPA fallback so the runner can prove soft-404 rejection.

Suggested fixture assertions:

```json
{
  "expected_findings": [
    {
      "path": "/api/v1/users",
      "status": "confirmed",
      "confidence": "high"
    },
    {
      "path": "/api/v1/orders",
      "status": "confirmed",
      "confidence": "high"
    },
    {
      "path": "/legacy/login",
      "status": "candidate",
      "confidence": "medium"
    },
    {
      "path": "/legacy/export",
      "status": "candidate",
      "confidence": "medium"
    }
  ],
  "expected_absent_paths": [
    "/api/v0/users",
    "/old",
    "/deprecated",
    "/api/v1/missing",
    "/assets/app.v1.js",
    "/products/gold"
  ],
  "forbidden_methods": [
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "TRACE",
    "CONNECT"
  ]
}
```

Optional compatibility fixtures:

* `juice-shop`: use only as a smoke target. Do not assert fixed old endpoint paths unless the fixture app explicitly adds them.
* `dvwa`: use only as a smoke target. Do not assert fixed old endpoint paths unless the fixture app explicitly adds them.
* `webgoat`: use only as a smoke target. Do not assert fixed old endpoint paths unless the fixture app explicitly adds them.

## Acceptance criteria

Implementation is accepted when:

* It is deterministic and does not call an LLM.
* It uses the shared `ScanTarget` and `Evidence` types.
* It defines only `OldEndpointSignature` and `OldEndpointFinding` as stub-specific persistence types.
* It sends only `HEAD` and `GET`.
* It uses bounded path generation.
* It learns and rejects soft-404 and generic fallback responses.
* It distinguishes candidate findings from confirmed findings.
* It marks disappeared old endpoints as `stale`.
* It deduplicates equivalent slash, redirect, and alias variants.
* It completes within the configured request and path budgets.
* It handles DNS errors, TLS errors, timeouts, rate limits, and connection failures without crashing the scan.
* It records enough Evidence for audit without storing secrets or full sensitive payloads.
* It never follows off-origin redirects.
* It is idempotent across repeated runs against the same fixture.
* It has unit tests for path normalization, stale-token matching, version-shadow generation, soft-404 rejection, finding classification, deduplication, and stale updates.
* It has integration tests against `old-endpoints-fixture`.
* It has negative tests proving forbidden methods are never sent.
* It produces no finding when all candidate paths are 404, 410, soft-404, homepage redirect, or generic fallback.

