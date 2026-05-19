---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 11
slug: robots-txt
status: done        # pending | in-progress | blocked | done
fixture: juice-shop # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.11 Robots.txt

> Phase 1 — Information gathering · Category: Public metadata

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

Detect and parse `/robots.txt` as public metadata. The runner uses it to learn crawl hints, sitemap locations, and paths the site owner chose to name publicly. A robots file is not a vulnerability by itself; it is evidence that may seed later, scoped, read-only checks.

## Inputs

The runner receives a shared `ScanTarget` and reads only the target origin’s root robots file.

Required input:

* `ScanTarget.base_url`
* `ScanTarget.host`

Optional config:

| Name                            |                    Default | Purpose                                                                         |
| ------------------------------- | -------------------------: | ------------------------------------------------------------------------------- |
| `timeout_ms`                    |                     `5000` | Per-request timeout.                                                            |
| `max_redirects`                 |                        `2` | Redirect limit for `/robots.txt`.                                               |
| `follow_cross_origin_redirects` |                    `false` | Whether to follow redirects to another origin. Default is no.                   |
| `max_body_bytes`                |                   `262144` | Maximum response body to read and persist.                                      |
| `max_extracted_paths`           |                      `200` | Maximum same-origin path hints to emit.                                         |
| `max_extracted_sitemaps`        |                       `50` | Maximum sitemap URLs to emit.                                                   |
| `user_agent`                    | project default scanner UA | HTTP user agent.                                                                |
| `request_headers`               |      project safe defaults | Extra headers allowed by the shared runner policy.                              |
| `store_raw_body`                |                     `true` | Store raw evidence body through the shared evidence store, subject to size cap. |

Credentials are not used for this spec. If credentials exist in the scan context, this runner must ignore them.

## Detection logic

### Request

Build the robots URL from the target origin:

```text
{scheme}://{host}:{optional_port}/robots.txt
```

Rules:

1. Use `GET`.
2. Do not send a request body.
3. Do not add query parameters.
4. Do not use credentials, cookies, bearer tokens, or session state.
5. Follow at most `max_redirects`.
6. Follow redirects only when the final URL stays within the same origin, unless `follow_cross_origin_redirects=true`.
7. Store every HTTP response in shared `Evidence`, including redirects if the shared evidence model supports request chains.

Recommended request headers:

```text
Accept: text/plain,*/*;q=0.8
User-Agent: {configured scanner user agent}
```

### Response classification

Classify the response deterministically:

| Condition                                                    | Classification                  | Finding behavior                                                                        |
| ------------------------------------------------------------ | ------------------------------- | --------------------------------------------------------------------------------------- |
| `200` with non-empty body                                    | `present`                       | Create confirmed robots metadata finding.                                               |
| `200` with empty or whitespace-only body                     | `empty`                         | Create confirmed empty robots finding.                                                  |
| `204`                                                        | `empty`                         | Create confirmed empty robots finding.                                                  |
| `301`, `302`, `303`, `307`, `308` followed to final response | `redirected`                    | Classify final response and record redirect chain.                                      |
| Redirect limit exceeded                                      | `redirect_limit_exceeded`       | Create candidate finding with low confidence.                                           |
| Cross-origin redirect not followed                           | `cross_origin_redirect_blocked` | Create candidate finding with low confidence.                                           |
| `401` or `403`                                               | `protected`                     | Create candidate finding; do not retry with credentials.                                |
| `404` or `410`                                               | `not_found`                     | No security finding; persist evidence and mark rejected if a finding object is created. |
| Other `4xx`                                                  | `client_error`                  | No confirmed finding.                                                                   |
| `5xx`                                                        | `server_error`                  | Candidate/stale depending on retry policy.                                              |
| Network/TLS/timeout error                                    | `unreachable`                   | No confirmed finding; persist error evidence if supported.                              |

Content-Type is advisory only. A valid robots body may be served as `text/plain`, `text/html`, `application/octet-stream`, or with no content type.

### Body handling

Process only the first `max_body_bytes`.

Decoding rules:

1. Strip UTF-8 BOM if present.
2. Decode as UTF-8 with replacement for invalid bytes.
3. Preserve the raw body or raw body hash in shared `Evidence`.
4. Parse from the normalized text.

Line parsing rules:

1. Split on `\n`.
2. Trim surrounding whitespace.
3. Ignore blank lines.
4. Remove comments beginning with `#`.
5. Treat directive names as case-insensitive.
6. Preserve directive values after trimming.
7. Treat malformed lines as parse warnings, not scanner errors.

Supported directives:

* `User-agent`
* `Allow`
* `Disallow`
* `Sitemap`
* `Crawl-delay`
* `Host`
* `Clean-param`

Unknown directives must be preserved as `unknown_directives` but must not fail parsing.

### Robots groups

Build groups using normal robots semantics:

* A group begins with one or more `User-agent` lines.
* `Allow` and `Disallow` lines belong to the current group.
* A new `User-agent` after rules starts a new group.
* `Sitemap` may appear anywhere and is global.
* Empty `Disallow:` means “nothing disallowed” and must not be recorded as a path hint.

The runner does not need to decide crawl permission for this spec. It only extracts public metadata.

### Extracted signals

Create deterministic signatures for these signals:

| Signal                 | Rule                                                         |
| ---------------------- | ------------------------------------------------------------ |
| `robots_present`       | Response is `200` or `204`.                                  |
| `robots_empty`         | Response body is empty or whitespace-only.                   |
| `robots_protected`     | Response is `401` or `403`.                                  |
| `robots_redirect`      | `/robots.txt` redirected before final response.              |
| `sitemap_declared`     | At least one valid `Sitemap:` URL exists.                    |
| `same_origin_sitemap`  | Sitemap URL origin matches target origin.                    |
| `cross_origin_sitemap` | Sitemap URL origin differs from target origin.               |
| `disallowed_path_hint` | Non-empty `Disallow:` path found.                            |
| `allowed_path_hint`    | Non-empty `Allow:` path found.                               |
| `sensitive_path_hint`  | A path matches the deterministic sensitive-path rules below. |
| `parse_warning`        | Malformed or unsupported lines were seen.                    |

Sensitive path matching is string/regex based only. It must not make a vulnerability claim.

A path is sensitive-looking when a normalized lowercase path contains one or more of these segments or filenames:

```text
admin
administrator
backup
backups
bak
old
debug
dev
staging
test
tmp
private
internal
config
configs
secret
secrets
token
tokens
key
keys
db
database
dump
sql
log
logs
.env
.git
.svn
.hg
```

Examples that should match:

```text
/admin
/private/
/backup.zip
/.git/
/config.old
/db-dump.sql
```

Examples that should not match:

```text
/blog
/catalog
/assets/logo.svg
```

### Path normalization

Normalize extracted path hints before persistence:

1. Keep only values that start with `/`.
2. Drop values that are full external URLs for path hint purposes.
3. Preserve robots wildcards `*` and `$` in the raw value.
4. Create a normalized display value by trimming whitespace and collapsing repeated spaces.
5. Do not resolve wildcards into generated paths.
6. Do not request extracted paths in this spec.

### Confidence

Assign confidence deterministically:

| Condition                                                                                             | Confidence |
| ----------------------------------------------------------------------------------------------------- | ---------- |
| `200` or `204` response from target origin with parsed body                                           | `high`     |
| Same-origin redirect followed successfully                                                            | `high`     |
| Protected robots response                                                                             | `medium`   |
| Cross-origin redirect blocked                                                                         | `low`      |
| Redirect limit exceeded                                                                               | `low`      |
| Network/TLS/timeout/server error                                                                      | `low`      |
| Sensitive path hint from valid parsed robots body                                                     | `medium`   |
| Sensitive path hint plus exact high-risk filename such as `.env`, `.git`, `db-dump.sql`, `backup.zip` | `high`     |

Do not raise confidence based on hostname, fixture name, or expected app type.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

### `RobotsTxtSignature`

A deterministic observation extracted from `/robots.txt`.

```json
{
  "id": "uuid",
  "scan_target_id": "uuid",
  "evidence_id": "uuid",
  "kind": "robots_present | robots_empty | robots_protected | robots_redirect | sitemap_declared | same_origin_sitemap | cross_origin_sitemap | disallowed_path_hint | allowed_path_hint | sensitive_path_hint | parse_warning",
  "source_url": "https://example.com/robots.txt",
  "final_url": "https://example.com/robots.txt",
  "http_status": 200,
  "directive": "Disallow",
  "user_agents": ["*"],
  "raw_value": "/admin",
  "normalized_value": "/admin",
  "sitemap_url": null,
  "sensitive_indicators": ["admin"],
  "line_number": 12,
  "confidence": "low | medium | high",
  "created_at": "ISO-8601"
}
```

Field rules:

* `directive` is nullable for response-level signatures.
* `user_agents` is empty for global directives such as `Sitemap`.
* `raw_value` stores the directive value before path normalization.
* `normalized_value` stores the normalized path or directive value.
* `sitemap_url` is only set for sitemap signatures.
* `line_number` is nullable for response-level signatures.
* `sensitive_indicators` is empty unless `kind=sensitive_path_hint`.

### `RobotsTxtFinding`

A finding-level summary for the target’s robots metadata.

```json
{
  "id": "uuid",
  "scan_target_id": "uuid",
  "primary_evidence_id": "uuid",
  "signature_ids": ["uuid"],
  "url": "https://example.com/robots.txt",
  "final_url": "https://example.com/robots.txt",
  "status": "candidate | confirmed | rejected | stale",
  "classification": "present | empty | protected | not_found | redirected | cross_origin_redirect_blocked | redirect_limit_exceeded | client_error | server_error | unreachable",
  "title": "Robots.txt exposes public crawl metadata",
  "summary": "The target publishes robots.txt with disallowed path hints and sitemap references.",
  "http_status": 200,
  "content_type": "text/plain",
  "body_size_bytes": 512,
  "disallowed_paths_count": 4,
  "allowed_paths_count": 1,
  "sitemaps_count": 1,
  "sensitive_path_hints_count": 2,
  "same_origin_path_hints": ["/admin", "/backup.zip"],
  "same_origin_sitemaps": ["https://example.com/sitemap.xml"],
  "cross_origin_sitemaps": [],
  "parse_warnings": [],
  "confidence": "low | medium | high",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

Status rules:

* `confirmed`: robots metadata was reached and classified from an HTTP response.
* `candidate`: response was protected, redirected away, truncated, malformed, or unavailable in a way that may be transient.
* `rejected`: `/robots.txt` was clearly absent, for example `404` or `410`.
* `stale`: previous confirmed finding is no longer supported by current evidence.

Severity should normally be informational if the shared model has severity. Sensitive path hints may help prioritize later checks but must not be persisted as a confirmed vulnerability by this spec alone.

### Evidence requirements

At minimum, persist evidence for:

* request method
* requested URL
* final URL
* status code
* response headers
* body hash
* body excerpt or full body within `max_body_bytes`
* redirect chain, if any
* TLS/network error details, if any

Do not persist cookies, authorization headers, or credentials.

## Safety

This check is read-only.

Allowed:

* One unauthenticated `GET /robots.txt`.
* Same-origin redirect following within `max_redirects`.
* Parsing the response body.
* Emitting path and sitemap hints for later scoped checks.

Not allowed:

* Requesting paths listed in `Disallow`.
* Requesting sitemap URLs in this spec.
* Sending credentials or cookies.
* Trying authenticated variants of `/robots.txt`.
* Mutating server state.
* Bypassing access controls.
* Treating `Disallow` as permission to scan a path.
* Treating `Disallow` as a prohibition override for the whole scanner.
* Creating a vulnerability finding from a path hint alone.
* Executing or rendering response content.
* Following URLs embedded in comments or unknown directives.

PII and secret handling:

* Robots files are public metadata, but path names may contain names, project codes, or secret-looking strings.
* Store only capped body evidence and extracted values needed for audit.
* Use the shared redaction utilities if a directive value looks like a token, password, API key, or session ID.
* Do not send robots content to an LLM.

AI involvement: `None`.

Deterministic gap: none for MVP. Parsing, classification, sensitive-path matching, and confidence are rule-based.

## Pass/fail check

### Positive assertions

A passing implementation must:

1. Request exactly `GET {origin}/robots.txt`.
2. Use the normalized target origin from `ScanTarget.base_url`.
3. Persist shared `Evidence` for the HTTP response or network error.
4. Return `rejected` or no confirmed finding for `404` and `410`.
5. Return `confirmed` for reachable `200` robots responses.
6. Return `confirmed` for empty reachable robots responses with classification `empty`.
7. Parse `User-agent`, `Allow`, `Disallow`, and `Sitemap` case-insensitively.
8. Ignore empty `Disallow:` values as path hints.
9. Extract same-origin path hints only from values beginning with `/`.
10. Extract sitemap URLs from `Sitemap:` directives.
11. Mark cross-origin sitemap URLs as cross-origin, not same-origin.
12. Flag sensitive-looking path hints using only deterministic matching.
13. Cap body read at `max_body_bytes`.
14. Cap extracted paths at `max_extracted_paths`.
15. Handle malformed lines without crashing.
16. Handle TLS, timeout, and network errors gracefully.
17. Produce stable output for repeated runs against the same evidence.

### Negative assertions

A passing implementation must not:

1. Modify the YAML frontmatter or shared schema.
2. Send POST, PUT, PATCH, DELETE, OPTIONS, or TRACE.
3. Send a request body.
4. Send credentials, cookies, bearer tokens, or session headers.
5. Fetch paths found in `Disallow` or `Allow`.
6. Fetch sitemap URLs.
7. Follow cross-origin redirects unless explicitly enabled.
8. Generate paths from wildcard robots patterns.
9. Treat a robots path hint as proof that the path exists.
10. Treat a robots path hint as proof of a vulnerability.
11. Hard-code expected robots behavior for Juice Shop, DVWA, WebGoat, or any hostname.
12. Fail the whole scan because `/robots.txt` is absent.
13. Execute JavaScript, HTML, or any content returned from `/robots.txt`.
14. Send robots content to an LLM.
15. Log secrets, authorization headers, cookies, or full uncapped bodies.

### Example expected outcomes

For this response:

```text
HTTP/1.1 200 OK
Content-Type: text/plain

User-agent: *
Disallow: /admin
Disallow: /backup.zip
Allow: /assets/
Sitemap: https://example.com/sitemap.xml
```

Expected:

* finding status: `confirmed`
* classification: `present`
* `disallowed_paths_count=2`
* `allowed_paths_count=1`
* `sitemaps_count=1`
* sensitive path signatures for `/admin` and `/backup.zip`
* no requests to `/admin`, `/backup.zip`, `/assets/`, or `/sitemap.xml`

For this response:

```text
HTTP/1.1 404 Not Found
Content-Type: text/html

not found
```

Expected:

* no confirmed robots metadata finding
* evidence persisted
* status `rejected` if a finding row is created
* no retry with alternative paths

## Test fixtures

Primary fixture: `juice-shop`.

Add a fixture route or static file that exposes:

```text
User-agent: *
Disallow: /admin
Disallow: /ftp/
Disallow: /backup.zip
Allow: /assets/
Sitemap: http://juice-shop.local/sitemap.xml
```

Expected fixture behavior:

* `/robots.txt` returns `200`.
* Content-Type may be `text/plain`.
* The runner detects three disallowed path hints.
* The runner detects one allowed path hint.
* The runner detects one sitemap.
* The runner flags `/admin` and `/backup.zip` as sensitive path hints.
* The runner does not request `/admin`, `/ftp/`, `/backup.zip`, `/assets/`, or `/sitemap.xml`.

Additional fixture cases may be implemented as small HTTP test servers instead of full vulnerable apps:

| Fixture slug                   | Behavior                                                     |
| ------------------------------ | ------------------------------------------------------------ |
| `robots-missing`               | `/robots.txt` returns `404`.                                 |
| `robots-empty`                 | `/robots.txt` returns `200` with empty body.                 |
| `robots-protected`             | `/robots.txt` returns `403`.                                 |
| `robots-redirect-same-origin`  | `/robots.txt` redirects to `/static/robots.txt`.             |
| `robots-redirect-cross-origin` | `/robots.txt` redirects to another origin.                   |
| `robots-malformed`             | Contains malformed lines and unknown directives.             |
| `robots-large`                 | Body exceeds `max_body_bytes`.                               |
| `robots-wildcards`             | Contains wildcard values such as `/private/*` and `/*.bak$`. |

## Acceptance criteria

The implementation is acceptable when:

1. It is idempotent: repeated scans against unchanged evidence produce the same signatures and finding summary.
2. It completes within the per-target request budget using one initial request plus bounded redirects.
3. It does not request any path discovered inside robots content.
4. It handles missing, empty, protected, redirected, malformed, oversized, and unreachable robots responses.
5. It uses shared `ScanTarget` and `Evidence` without redefining them.
6. It persists only `RobotsTxtSignature` and `RobotsTxtFinding` as stub-specific types.
7. It marks confidence using deterministic rules.
8. It records sensitive-looking paths as metadata, not as confirmed vulnerabilities.
9. It keeps all detection logic deterministic and uses no AI.
10. It passes tests for positive parsing, negative safety behavior, redirect handling, size caps, malformed content, and stable repeated output.

