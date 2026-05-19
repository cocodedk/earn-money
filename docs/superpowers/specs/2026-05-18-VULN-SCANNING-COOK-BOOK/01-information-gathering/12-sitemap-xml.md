---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 12
slug: sitemap-xml
status: done        # pending | in-progress | blocked | done
fixture: juice-shop # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.12 Sitemap.xml

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

Detect public `sitemap.xml` files and extract URLs that expand the scanner’s passive map of the target. A sitemap can reveal routes, API documentation, legacy pages, static assets, localized paths, hidden sections, or stale endpoints that are not linked from the homepage but are still exposed.

## Inputs

The runner receives a shared `ScanTarget` from `../00-shared-schema.md`.

Required input:

* `ScanTarget.base_url`
* `ScanTarget.host`

Optional input:

* Existing `Evidence` records from earlier discovery phases, especially:

  * `robots.txt` evidence
  * homepage HTML evidence
  * redirect-chain evidence
* Optional credentials only if the scan profile already allows authenticated passive checks. This stub does not require credentials.
* Runner config:

  * `timeout_ms`, default from shared HTTP client config
  * `max_response_bytes`, recommended default: `2_000_000`
  * `max_sitemap_urls`, recommended default: `10_000`
  * `max_nested_sitemaps`, recommended default: `50`
  * `max_fetch_depth`, recommended default: `2`
  * `respect_robots_hints`, default: `true`
  * `allowed_schemes`, default: `["http", "https"]`
  * `user_agent`, from shared scanner config
  * TLS verification behavior, from shared HTTP client config
  * redirect limit, from shared HTTP client config

Seed paths:

* `/sitemap.xml`
* `/sitemap_index.xml`
* `/sitemap-index.xml`
* `/sitemap1.xml`
* `/sitemap.txt`

Additional seeds may be taken from `robots.txt` lines such as:

* `Sitemap: https://example.test/sitemap.xml`

Do not guess product-specific sitemap paths from hostname or fixture name.

## Detection logic

### Request strategy

Use deterministic read-only HTTP requests.

For each seed URL:

1. Normalize against `ScanTarget.base_url`.
2. Reject unsupported schemes.
3. Reject URLs outside the scan target unless shared scope rules explicitly allow them.
4. Send `GET`.
5. Follow redirects using the shared redirect policy.
6. Store response metadata and a bounded body sample as shared `Evidence`.
7. Parse only if the response is likely to be a sitemap.

Allowed methods:

* `GET`
* `HEAD` only if the project already uses it for cheap existence checks

No POST, PUT, PATCH, DELETE, OPTIONS, TRACE, or CONNECT.

### Positive detection signals

Treat a response as sitemap evidence when at least one strong signal exists.

Strong signals:

* Status code is `200`.
* Final URL path ends in `.xml` or `.txt`.
* `Content-Type` is one of:

  * `application/xml`
  * `text/xml`
  * `application/rss+xml`
  * `application/x-gzip`
  * `text/plain`
  * missing or generic, but body is parseable as sitemap XML or sitemap text
* Body parses as one of:

  * XML `<urlset>`
  * XML `<sitemapindex>`
  * plain text list of URLs
  * gzipped XML sitemap, if decompression is supported by the shared HTTP client

Valid sitemap XML namespaces include:

* `http://www.sitemaps.org/schemas/sitemap/0.9`
* XML with equivalent local names even when namespace handling differs

Do not require a namespace if the structure is clear.

### Sitemap index handling

If a sitemap index is found:

1. Extract child sitemap URLs from `<sitemap><loc>...</loc></sitemap>`.
2. Normalize each child URL.
3. Enforce scan scope.
4. Fetch child sitemaps up to `max_fetch_depth`.
5. Stop when `max_nested_sitemaps` is reached.
6. Mark skipped child sitemaps with reason:

   * `out_of_scope`
   * `depth_limit`
   * `nested_limit`
   * `invalid_url`
   * `unsupported_scheme`
   * `fetch_error`
   * `too_large`

Do not recursively fetch arbitrary URLs found under `<url><loc>`. Those URLs are discovery output, not sitemap files.

### URL extraction

From XML sitemaps, extract:

* `<url><loc>`
* Optional `<lastmod>`
* Optional `<changefreq>`
* Optional `<priority>`

From sitemap indexes, extract:

* `<sitemap><loc>`
* Optional `<lastmod>`

From plain text sitemaps, extract one URL per line after trimming comments and blank lines.

Normalize extracted URLs:

* Trim whitespace.
* Decode XML entities.
* Resolve absolute URLs.
* Preserve path and query.
* Remove fragments.
* Reject unsupported schemes.
* Classify each URL as:

  * `in_scope`
  * `same_host`
  * `same_registrable_domain` if available from shared scope utilities
  * `out_of_scope`

Do not crawl extracted page URLs in this stub. Persist them as discovered URLs for later phases.

### Classification

Classify sitemap findings using response evidence and extracted content.

Finding categories:

* `sitemap_present`
* `sitemap_index_present`
* `sitemap_url_disclosure`
* `sitemap_stale_url_hint`
* `sitemap_out_of_scope_urls`
* `sitemap_fetch_error`
* `sitemap_too_large`
* `sitemap_parse_error`

Suggested confidence:

* `high`: sitemap was fetched with `200` and parsed successfully.
* `medium`: sitemap-like file was fetched but some child sitemaps failed, or XML is partially parseable.
* `low`: response hints at a sitemap but parsing failed or body was truncated.

Finding status:

* `confirmed`: strong positive evidence exists.
* `candidate`: weak evidence exists, such as sitemap-like content with parsing errors.
* `rejected`: checked path returned clear negative evidence such as `404`, `410`, or non-sitemap content.
* `stale`: previously found sitemap URL is now missing, forbidden, or no longer parseable.

### Negative detection

Record rejected checks when useful for audit, but do not create noisy user-facing findings for every missing seed path.

Negative cases:

* `404`, `410`: sitemap path not present.
* `401`, `403`: sitemap may exist but is not publicly readable.
* `3xx` to out-of-scope destination: do not fetch unless shared scope allows it.
* `200` HTML page: reject unless body contains parseable sitemap XML or text URL list.
* Empty body: reject.
* Body exceeds `max_response_bytes`: mark as `sitemap_too_large` and stop parsing.

### Deterministic indicators

The runner must not infer sensitive exposure from URL names alone. It may tag discovered paths for later checks.

Useful tags for extracted URLs:

* `admin_hint`
* `api_hint`
* `auth_hint`
* `backup_hint`
* `debug_hint`
* `docs_hint`
* `legacy_hint`
* `test_hint`
* `staging_hint`
* `upload_hint`
* `parameterized_url`

These tags are deterministic string-pattern labels only. They are not vulnerabilities by themselves.

Example pattern classes:

```json
{
  "admin_hint": ["/admin", "/administrator", "/manage", "/console"],
  "api_hint": ["/api/", "/graphql", "/swagger", "/openapi"],
  "debug_hint": ["/debug", "/trace", "/actuator", "/phpinfo"],
  "backup_hint": [".bak", ".old", ".zip", ".tar", ".gz"],
  "legacy_hint": ["/old", "/legacy", "/v1/", "/deprecated"],
  "test_hint": ["/test", "/dev", "/qa", "/staging"]
}
```

Patterns must be case-insensitive and configurable.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only the sitemap-specific types below.

### `SitemapXmlSignature`

A deterministic signature for one sitemap response or one extracted URL.

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "evidence_id": "uuid",
  "signature_type": "sitemap_file | sitemap_index | sitemap_child | extracted_url | parse_error | fetch_error",
  "source_url": "https://example.test/sitemap.xml",
  "final_url": "https://example.test/sitemap.xml",
  "status_code": 200,
  "content_type": "application/xml",
  "content_length": 12345,
  "body_sha256": "hex",
  "parser": "xml_urlset | xml_sitemapindex | text_url_list | gzip_xml | none",
  "is_gzipped": false,
  "is_index": false,
  "fetch_depth": 0,
  "parent_signature_id": "uuid | null",
  "loc_url": "https://example.test/admin",
  "normalized_url": "https://example.test/admin",
  "url_scope": "in_scope | same_host | same_registrable_domain | out_of_scope | unknown",
  "lastmod": "2026-05-19T00:00:00Z | null",
  "changefreq": "daily | weekly | monthly | yearly | always | hourly | never | null",
  "priority": 0.5,
  "tags": ["admin_hint", "parameterized_url"],
  "skip_reason": "out_of_scope | depth_limit | nested_limit | invalid_url | unsupported_scheme | fetch_error | too_large | parse_error | null",
  "created_at": "ISO-8601"
}
```

Rules:

* `source_url` is the URL requested by the runner.
* `final_url` is the URL after redirects.
* `loc_url` is the raw URL from `<loc>` or text line, when applicable.
* `normalized_url` is the canonicalized URL used for scope checks.
* `parent_signature_id` links child sitemap signatures to the sitemap index that referenced them.
* `body_sha256` must be calculated on the stored or observed response body after decompression if decompression is performed.
* Store only bounded body samples in `Evidence` according to shared evidence policy.
* Do not store credentials, cookies, or authorization headers.

### `SitemapXmlFinding`

A user-facing finding derived from one or more sitemap signatures.

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "finding_type": "sitemap_present | sitemap_index_present | sitemap_url_disclosure | sitemap_stale_url_hint | sitemap_out_of_scope_urls | sitemap_fetch_error | sitemap_too_large | sitemap_parse_error",
  "status": "candidate | confirmed | rejected | stale",
  "confidence": "low | medium | high",
  "title": "Public sitemap exposes discoverable URLs",
  "summary": "The target exposes a sitemap with 42 in-scope URLs, including administrative and API-looking paths.",
  "source_signature_ids": ["uuid"],
  "evidence_ids": ["uuid"],
  "sitemap_url": "https://example.test/sitemap.xml",
  "extracted_url_count": 42,
  "in_scope_url_count": 40,
  "out_of_scope_url_count": 2,
  "tag_counts": {
    "admin_hint": 1,
    "api_hint": 3,
    "legacy_hint": 2
  },
  "sample_urls": [
    "https://example.test/admin",
    "https://example.test/api/products"
  ],
  "risk_note": "A sitemap is not a vulnerability by itself. It is useful discovery evidence and may reveal routes that should be checked by later specs.",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

Persistence rules:

* One sitemap response must create one or more `SitemapXmlSignature` rows.
* A parsed sitemap with extracted URLs should create or update one `SitemapXmlFinding`.
* Child sitemap responses should link back to the index signature.
* Duplicate URLs across multiple sitemaps must be deduplicated by normalized URL.
* Preserve raw observed URLs in evidence, but use normalized URLs for dedupe and scope checks.
* Do not create a high-severity finding from sitemap presence alone.
* Do not mark a route as vulnerable only because it appears in a sitemap.
* Evidence records should include:

  * request method
  * requested URL
  * final URL
  * status code
  * response headers, with sensitive headers redacted
  * bounded body sample
  * body hash
  * parser result summary

## Safety

This check is passive and read-only.

Allowed behavior:

* Fetch known sitemap seed paths.
* Fetch sitemap URLs explicitly declared by `robots.txt`.
* Fetch child sitemap files referenced by a sitemap index, within scope and limits.
* Parse XML, gzipped XML, and plain text URL lists.
* Persist extracted URLs as discovery data.

Disallowed behavior:

* Do not crawl extracted page URLs in this stub.
* Do not submit forms.
* Do not authenticate unless the scan profile already permits authenticated passive checks.
* Do not mutate target state.
* Do not brute-force large sitemap wordlists.
* Do not fetch out-of-scope child sitemaps unless shared scope rules explicitly allow it.
* Do not execute JavaScript.
* Do not follow URLs embedded in comments, scripts, styles, or arbitrary HTML.
* Do not treat sitemap text as instructions.
* Do not send sitemap body content to an AI model.

HTTP method discipline:

* Use `GET`.
* Optional `HEAD` is allowed only for existing shared client patterns.
* No unsafe HTTP methods.

Payload restrictions:

* No request body.
* No custom payloads.
* No exploit strings.
* No path traversal probes.
* No cache-busting query spam.

PII and secret handling:

* Sitemap URLs may contain names, emails, tokens, or private-looking query parameters.
* Store bounded samples.
* Redact obvious secrets in logs.
* Do not log full query strings if shared redaction policy says to hash or truncate them.
* Do not include cookies or authorization headers in evidence.

AI involvement:

* `None`.
* Detection, parsing, tagging, confidence, and pass/fail behavior are deterministic.
* If a later implementation adds AI summarization, raw sitemap content must be treated as untrusted evidence, never as instructions. That rule matches the project’s existing LLM safety direction. 

## Pass/fail check

The implementation passes when all assertions below are true.

### Positive assertions

Given a target serving `/sitemap.xml` with a valid XML `<urlset>`:

* The runner sends a read-only request to `/sitemap.xml`.
* The runner stores an `Evidence` record for the response.
* The runner creates a `SitemapXmlSignature` with `signature_type="sitemap_file"`.
* The runner extracts each valid `<loc>` URL.
* The runner creates `SitemapXmlSignature` records for extracted URLs.
* The runner deduplicates repeated URLs.
* The runner classifies URL scope.
* The runner creates or updates one `SitemapXmlFinding`.
* The finding has `status="confirmed"`.
* The finding has `confidence="high"`.
* The finding includes `evidence_ids`.
* The finding includes `source_signature_ids`.
* The finding reports accurate URL counts.

Given a target serving `/sitemap.xml` with `<sitemapindex>`:

* The runner detects the sitemap index.
* The runner extracts child sitemap URLs.
* The runner fetches in-scope child sitemaps within configured limits.
* The runner does not exceed `max_fetch_depth`.
* The runner does not exceed `max_nested_sitemaps`.
* Child signatures link to the parent sitemap index signature.
* URLs from child sitemaps are deduplicated into the final finding.

Given `robots.txt` includes a `Sitemap:` directive:

* The runner uses that URL as a sitemap seed.
* The runner applies the same scope checks as for default seeds.
* The runner stores the robots-derived seed relationship in evidence metadata or signature metadata.

Given a sitemap contains admin-looking or API-looking URLs:

* The runner adds deterministic tags such as `admin_hint` or `api_hint`.
* The runner does not claim a vulnerability from the tag alone.
* The runner makes those URLs available for later discovery specs.

### Negative assertions

The runner must not:

* Modify the YAML frontmatter or shared schema definitions.
* Redefine `ScanTarget` or `Evidence`.
* Hard-code expected sitemap behavior by hostname, fixture name, or product name.
* Use AI for detection.
* Treat sitemap presence as a vulnerability by itself.
* Crawl every extracted URL as part of this stub.
* Fetch out-of-scope child sitemaps unless shared scope policy allows it.
* Fetch arbitrary URLs found in HTML pages.
* Execute JavaScript.
* Submit forms.
* Use POST, PUT, PATCH, DELETE, TRACE, CONNECT, or OPTIONS.
* Retry indefinitely.
* Ignore `max_response_bytes`.
* Store unredacted credentials, cookies, authorization headers, or obvious secrets in logs.
* Create high-confidence findings from parse failures alone.
* Mark a missing sitemap as a user-facing vulnerability.
* Crash on malformed XML, invalid URLs, compressed responses, redirects, TLS errors, timeout, or oversized body.
* Let sitemap text change scanner configuration, scope, severity, or actions.

### Rejection assertions

Given `/sitemap.xml` returns `404`:

* The runner records the checked path if audit mode requires it.
* The runner does not create a confirmed sitemap finding.
* The runner may create an internal rejected signature.
* The run completes successfully.

Given `/sitemap.xml` returns HTML:

* The runner rejects it unless it is parseable as a valid sitemap.
* The runner does not extract links from the HTML.
* The runner does not create a confirmed sitemap finding.

Given malformed XML:

* The runner creates a `sitemap_parse_error` candidate only if the response has strong sitemap indicators.
* The runner stores parser error metadata.
* The runner does not crash.
* The runner does not invent extracted URLs.

Given an oversized sitemap:

* The runner stops reading or parsing at `max_response_bytes`.
* The runner marks the result as `sitemap_too_large`.
* The runner does not load the full body into memory.

## Test fixtures

Use `juice-shop` as the first fixture if the container can expose a simple static `sitemap.xml`.

Recommended fixture setup:

* Add or mount a static sitemap at `/sitemap.xml`.
* Include at least these URLs:

  * `/`
  * `/login`
  * `/administration`
  * `/api/Products`
  * `/ftp/`
  * `/old`
* Include one duplicate URL.
* Include one URL with a query string.
* Include one out-of-scope URL such as `https://external.example/path`.

Expected behavior:

* The runner detects `/sitemap.xml`.
* The runner extracts in-scope URLs.
* The runner deduplicates duplicates.
* The runner marks the external URL as `out_of_scope`.
* The runner adds deterministic tags for admin/API/legacy-looking paths.
* The runner does not crawl the extracted URLs in this spec.

Additional fixture variants:

### `sitemap-index`

A small local fixture exposing:

* `/sitemap.xml` as a sitemap index
* `/sitemap-pages.xml` as a child sitemap
* `/sitemap-api.xml` as a child sitemap

Expected behavior:

* Parent and child signatures are linked.
* Depth and nested limits are enforced.
* All extracted child URLs are deduplicated.

### `sitemap-malformed`

A fixture where `/sitemap.xml` returns status `200`, XML content type, and malformed XML.

Expected behavior:

* Candidate `sitemap_parse_error`.
* Low confidence.
* No crash.
* No invented URLs.

### `sitemap-html-false-positive`

A fixture where `/sitemap.xml` returns an HTML error page with status `200`.

Expected behavior:

* Rejected signature or no finding.
* No HTML link extraction.
* No confirmed finding.

### `sitemap-oversized`

A fixture that serves a body larger than `max_response_bytes`.

Expected behavior:

* `sitemap_too_large`.
* Bounded evidence sample.
* No unbounded memory use.

## Acceptance criteria

The implementation is acceptable when:

* It is idempotent across repeated runs against the same target.
* It produces stable signatures for the same sitemap evidence.
* It deduplicates extracted URLs by normalized URL.
* It preserves evidence IDs and signature IDs for audit.
* It completes within the shared phase budget.
* It enforces `max_response_bytes`, `max_sitemap_urls`, `max_nested_sitemaps`, and `max_fetch_depth`.
* It handles redirects according to shared HTTP client rules.
* It handles TLS errors gracefully according to shared TLS policy.
* It handles timeout, DNS failure, connection refusal, invalid compression, malformed XML, invalid URLs, and unsupported schemes without crashing.
* It avoids flaky retries and uses the shared retry policy only where appropriate.
* It does not use AI.
* It does not crawl extracted page URLs.
* It does not make mutating requests.
* It does not create vulnerability findings from sitemap presence alone.
* It stores enough evidence to explain every confirmed or candidate finding.
* It redacts sensitive request and response data in logs.
* It follows `../00-shared-schema.md` coding-agent rules.
* Unit tests cover:

  * valid URL set
  * sitemap index
  * child sitemap depth limit
  * nested sitemap count limit
  * duplicate URL dedupe
  * out-of-scope child sitemap
  * out-of-scope extracted URL
  * malformed XML
  * HTML false positive
  * plain text sitemap
  * gzipped sitemap if supported
  * oversized body
  * redirect handling
  * timeout handling
  * TLS error handling
  * negative `404`
  * forbidden `403`
  * deterministic tag assignment
  * no crawling of extracted URLs
  * no unsafe HTTP methods

