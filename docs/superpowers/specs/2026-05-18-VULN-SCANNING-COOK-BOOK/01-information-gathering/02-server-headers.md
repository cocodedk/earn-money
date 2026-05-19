---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 2
slug: server-headers
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.2 Server headers

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

Detect server and infrastructure hints exposed through HTTP response headers. The runner uses these hints to fingerprint web servers, reverse proxies, frameworks, CDNs, security middleware, cache layers, and deployment platforms without making assumptions from hostnames or target labels.

## Inputs

### Required

* `ScanTarget` from `../00-shared-schema.md`

  * Use `base_url` as the starting URL.
  * Use `host` only as target metadata.
  * Do not infer expected technology from `host`.

### Optional

* Existing `Evidence` records from previous passive requests, if available.
* Runner HTTP config:

  * `timeout_seconds`, default `10`
  * `max_redirects`, default `3`
  * `user_agent`, default project scanner user agent
  * `verify_tls`, default project setting
  * `follow_redirects`, default `true`
* Optional credentials from the shared runner context, if the project already supports authenticated read-only scans.

  * This spec does not require credentials.
  * Do not attempt login here.

### Output

One or more `ServerHeadersFinding` records linked to one or more `Evidence` records.

## Detection logic

Detection is deterministic and read-only.

### Request strategy

The runner should collect headers from a small set of passive requests:

1. `HEAD /`
2. `GET /` if `HEAD` is unsupported, blocked, or returns no useful headers.
3. Redirect responses seen while resolving `/`, up to `max_redirects`.
4. Optional `GET /favicon.ico` only if the runner already fetches it in Phase 1.
5. Optional `GET /robots.txt` only if the runner already fetches it in Phase 1.

Do not crawl. Do not brute force paths. Do not send payloads.

### Useful response headers

Inspect response headers case-insensitively. Preserve original casing in evidence, but normalize names for matching.

Collect values from:

* `Server`
* `X-Powered-By`
* `X-AspNet-Version`
* `X-AspNetMvc-Version`
* `X-Generator`
* `X-Drupal-Cache`
* `X-Drupal-Dynamic-Cache`
* `X-Varnish`
* `Via`
* `X-Cache`
* `CF-Cache-Status`
* `CF-Ray`
* `X-Amz-Cf-Id`
* `X-Amz-Cf-Pop`
* `X-Served-By`
* `X-Timer`
* `X-Backend-Server`
* `X-Backend`
* `X-Proxy-Cache`
* `X-Nginx-Cache`
* `X-Envoy-Upstream-Service-Time`
* `X-Kong-Upstream-Latency`
* `X-Kong-Proxy-Latency`
* `X-Request-Id`
* `X-Correlation-Id`
* `Strict-Transport-Security`
* `Content-Security-Policy`
* `X-Frame-Options`
* `X-Content-Type-Options`
* `Referrer-Policy`
* `Permissions-Policy`

Security headers are not vulnerabilities in this spec. They are supporting fingerprint evidence only. Missing security headers must not create findings here.

### Signature matching

Create a deterministic signature table. Match against normalized header names and values.

Examples:

| Header evidence                         |  Technology hint | Confidence |
| --------------------------------------- | ---------------: | ---------: |
| `Server: nginx`                         |          `nginx` |     `high` |
| `Server: Apache`                        |   `apache_httpd` |     `high` |
| `Server: Microsoft-IIS/10.0`            |            `iis` |     `high` |
| `X-Powered-By: Express`                 |        `express` |     `high` |
| `X-Powered-By: PHP/8.2.0`               |            `php` |     `high` |
| `X-AspNet-Version` present              |         `aspnet` |     `high` |
| `X-AspNetMvc-Version` present           |     `aspnet_mvc` |     `high` |
| `CF-Ray` or `CF-Cache-Status` present   |     `cloudflare` |     `high` |
| `X-Amz-Cf-Id` present                   | `aws_cloudfront` |     `high` |
| `X-Varnish` present                     |        `varnish` |     `high` |
| `X-Served-By` with Fastly-style value   |         `fastly` |   `medium` |
| `Via` contains `varnish`                |        `varnish` |   `medium` |
| `Via` contains `envoy`                  |          `envoy` |   `medium` |
| `X-Envoy-Upstream-Service-Time` present |          `envoy` |     `high` |
| `X-Kong-Upstream-Latency` present       |           `kong` |     `high` |

### Version extraction

Extract version only when it appears directly in the header value.

Examples:

* `Server: nginx/1.24.0` → version `1.24.0`
* `Server: Apache/2.4.58` → version `2.4.58`
* `X-Powered-By: PHP/8.2.12` → version `8.2.12`
* `Server: Microsoft-IIS/10.0` → version `10.0`

Do not guess versions from vague values.

Version strings must be stored as observed strings, not normalized semver, unless the project already has a shared version parser.

### Conflict handling

Multiple layers may be present. Store all credible hints.

Examples:

* `Server: cloudflare` and `X-Powered-By: Express` means:

  * edge layer: `cloudflare`
  * app hint: `express`
* `Via: 1.1 varnish` and `Server: nginx` means:

  * proxy/cache hint: `varnish`
  * server hint: `nginx`

Do not reject one hint only because another hint exists.

### Confidence rules

Use:

* `high` when a specific header directly names the technology.
* `medium` when the header strongly implies the technology but does not name it directly.
* `low` when the signal is weak, generic, or ambiguous.

Do not emit findings from `low` signals unless the implementation already stores weak candidates. If stored, mark them `candidate`.

### Status rules

* `confirmed`: direct header evidence identifies the technology.
* `candidate`: indirect or weak evidence suggests the technology.
* `rejected`: a previous candidate was contradicted by stronger evidence in the same scan.
* `stale`: previous finding no longer appears in current evidence.

For this spec’s first implementation, it is acceptable to emit only `candidate` and `confirmed`.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

### `ServerHeaderSignature`

```json
{
  "id": "string",
  "header_name": "string",
  "value_pattern": "string",
  "match_type": "exact | contains | regex",
  "technology": "string",
  "technology_category": "web_server | app_runtime | framework | proxy | cdn | cache | load_balancer | security_middleware | unknown",
  "version_regex": "string | null",
  "confidence": "low | medium | high"
}
```

Rules:

* `header_name` is normalized lowercase.
* `value_pattern` is deterministic.
* `regex` must be safe and bounded.
* Avoid broad patterns that match unrelated text.
* Do not use AI-generated signatures at runtime.

### `ServerHeadersFinding`

```json
{
  "id": "uuid",
  "scan_target_id": "uuid",
  "evidence_ids": ["uuid"],
  "technology": "string",
  "technology_category": "web_server | app_runtime | framework | proxy | cdn | cache | load_balancer | security_middleware | unknown",
  "matched_header_name": "string",
  "matched_header_value": "string",
  "version": "string | null",
  "confidence": "low | medium | high",
  "status": "candidate | confirmed | rejected | stale",
  "first_seen_at": "ISO-8601",
  "last_seen_at": "ISO-8601",
  "source": "server_headers"
}
```

### Evidence requirements

For every finding, persist evidence containing:

* request method
* final URL
* response status code
* response headers
* redirect chain headers, if relevant
* timestamp
* content hash or header hash if supported by shared `Evidence`
* TLS error metadata if the request failed before headers were received

Do not store cookies, tokens, or credentials in raw header evidence. Redact sensitive headers before persistence using the shared redaction utility.

Redact at least:

* `Set-Cookie`
* `Cookie`
* `Authorization`
* `Proxy-Authorization`
* `X-Api-Key`
* `X-Auth-Token`

## Safety

This check is passive and read-only.

### Allowed

* `HEAD`
* `GET`
* Following normal redirects within runner limits
* Reading response headers
* Persisting redacted evidence

### Not allowed

* `POST`, `PUT`, `PATCH`, `DELETE`
* Login attempts
* Form submission
* Payload injection
* Path brute forcing
* Header spoofing to trigger alternate behavior
* Exploit checks
* Version vulnerability lookup in this spec
* Creating a vulnerability finding only because a version is old

### PII and secrets

Headers can contain cookies, tokens, internal hostnames, request IDs, and backend names.

Rules:

* Redact known secret-bearing headers before logging or persistence.
* Do not print full response headers to normal logs.
* Store raw headers only if the project has secure evidence storage.
* Treat internal backend names as sensitive metadata.
* Do not send header evidence to AI.

### AI involvement

AI is `None`.

There is no deterministic gap that requires AI for this spec. All detection comes from header names, header values, and fixed signature matching.

## Pass/fail check

### Positive assertions

The implementation passes when:

* It sends at most one `HEAD /` and one fallback `GET /` for the base URL, excluding redirects.
* It captures headers from redirect responses and the final response.
* It normalizes header names for matching.
* It preserves observed header values in evidence after redaction.
* It detects `nginx` from `Server: nginx/1.24.0`.
* It extracts version `1.24.0` from `Server: nginx/1.24.0`.
* It detects `express` from `X-Powered-By: Express`.
* It detects `cloudflare` from `CF-Ray` or `CF-Cache-Status`.
* It detects `aws_cloudfront` from `X-Amz-Cf-Id`.
* It creates one `ServerHeadersFinding` per distinct technology hint.
* It links each finding to at least one `Evidence` record.
* It marks direct matches as `confirmed`.
* It marks indirect matches as `candidate` unless the signature says confidence is `high`.
* It handles unsupported `HEAD` by falling back to `GET /`.

### Negative assertions

The implementation must not:

* Hard-code hostname to expected technology.
* Create findings from missing security headers.
* Treat security headers as vulnerabilities in this spec.
* Use AI.
* Send mutating HTTP methods.
* Attempt authentication.
* Crawl paths.
* Brute force files or directories.
* Guess a version when no version appears in the header.
* Persist unredacted `Set-Cookie`, `Cookie`, `Authorization`, or API-token headers.
* Fail the whole scan because one request times out.
* Retry endlessly.
* Mark a stale previous finding as still confirmed when the current scan no longer has matching evidence.
* Call external vulnerability databases from this spec.

## Test fixtures

Use `juice-shop` as the first fixture because it is already expected in the local scanner environment and commonly exposes app/runtime headers through its HTTP stack.

Recommended fixture setup:

* `juice-shop`

  * Expected behavior:

    * Runner receives normal HTTP headers from `/`.
    * If `X-Powered-By: Express` is present, detect `express`.
    * If a reverse proxy is placed in front of the fixture, detect that proxy from headers without assuming Juice Shop itself changed.
  * The test must assert against actual response headers from the fixture, not the hostname.

Additional synthetic fixture responses should be added under the project’s HTTP fixture pattern:

* `server_headers/nginx.json`
* `server_headers/apache.json`
* `server_headers/iis.json`
* `server_headers/express.json`
* `server_headers/php.json`
* `server_headers/cloudflare.json`
* `server_headers/cloudfront.json`
* `server_headers/varnish.json`
* `server_headers/envoy.json`
* `server_headers/kong.json`
* `server_headers/redaction.json`
* `server_headers/head_405_get_fallback.json`
* `server_headers/redirect_chain.json`
* `server_headers/noisy_generic_headers.json`

Synthetic fixture requirements:

* Include request method.
* Include URL.
* Include status code.
* Include response headers.
* Include expected findings.
* Include expected redactions.

## Acceptance criteria

* The check is idempotent.
* The check is deterministic.
* The check uses only read-only HTTP methods.
* The check completes within the Phase 1 request budget.
* The check handles TLS failures gracefully and records failure evidence where the shared schema supports it.
* The check handles timeouts without crashing the scan.
* The check handles redirects within configured limits.
* The check handles duplicate headers and multi-value headers.
* The check treats header names case-insensitively.
* The check redacts sensitive headers before normal logging or persistence.
* The check produces stable finding IDs or stable deduplication keys if the project has that pattern.
* The check does not create vulnerability findings.
* The check does not depend on hostname-specific expectations.
* Unit tests cover signature matching, version extraction, redaction, redirect handling, `HEAD` fallback, stale handling, and negative assertions.
* Integration test runs against `juice-shop` or a project-approved local fixture without internet access.

