---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 14
slug: source-maps
status: done        # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.14 Source maps

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

Detect publicly reachable JavaScript or CSS source maps. Source maps often expose original source paths, comments, route names, framework structure, API client code, build metadata, and sometimes embedded source content. A runner cares because this can improve later passive checks, explain frontend behavior, and identify accidental source exposure without executing code or modifying the target.

## Inputs

The runner receives a shared `ScanTarget` and uses its `base_url` as the scan root.

Required input:

* `ScanTarget`
* HTTP client with redirect, timeout, TLS, and response-size controls
* shared evidence writer for `Evidence`

Optional inputs:

* `known_asset_urls`: previously discovered JavaScript or CSS asset URLs from crawling, HTML parsing, sitemap parsing, robots parsing, or framework detection
* `max_assets`: default `50`
* `max_map_fetches`: default `50`
* `max_response_bytes`: default `2_000_000`
* `max_source_content_bytes_persisted`: default `0`
* `request_timeout_seconds`: default `10`
* `follow_redirects`: default `true`, with same-origin final URL required unless global scanner policy allows otherwise
* `allowed_content_types`: default:

  * `application/json`
  * `application/octet-stream`
  * `text/plain`
  * empty or missing content type when the body parses as JSON
* `user_agent`: project default scanner user agent
* `respect_robots`: inherited from global scanner policy
* `credentials`: optional, but not used by default in this spec

Authentication is out of scope for the default runner. If credentials are present, this check still runs in public/passive mode unless a later authenticated profile explicitly enables authenticated asset fetching.

## Detection logic

The check is deterministic and read-only. It uses `GET` and optional `HEAD` only.

### Candidate asset collection

Build a bounded list of JavaScript and CSS asset URLs from:

1. `known_asset_urls` supplied by earlier runners.
2. The target homepage HTML, if no known assets are supplied or if the shared crawler has not run yet.
3. Same-origin HTML asset references:

   * `<script src="...">`
   * `<link rel="stylesheet" href="...">`
   * `<link rel="preload" as="script" href="...">`
   * `<link rel="modulepreload" href="...">`
4. Same-origin asset-like paths found in already persisted evidence, if the project has a safe shared asset index.

Only include URLs that are:

* same-origin with `ScanTarget.base_url`, unless the global scanner scope says otherwise
* `http` or `https`
* likely JavaScript or CSS by path or content type

Likely JavaScript paths include:

* `.js`
* `.mjs`
* `.cjs`
* `.jsx`
* `.ts` only if publicly served as a static asset

Likely CSS paths include:

* `.css`

Do not crawl arbitrary links from source maps. Source map `sources` entries are metadata, not fetch targets.

### Source map reference detection

For each candidate asset, fetch the asset with `GET`.

Record evidence for:

* request URL
* final URL after redirects
* status code
* content type
* response headers needed for audit
* bounded body excerpt or hash, following shared evidence rules

Search the response body for a source map reference.

JavaScript source map comment forms:

```text
//# sourceMappingURL=app.js.map
//@ sourceMappingURL=app.js.map
```

CSS source map comment form:

```text
/*# sourceMappingURL=app.css.map */
```

Extract the value after `sourceMappingURL=`.

Accept these reference types:

* relative URL: `app.js.map`
* absolute same-origin URL: `https://target.example/static/app.js.map`
* root-relative URL: `/static/app.js.map`

Handle query strings and fragments.

Reject these reference types:

* `data:` inline source maps
* `javascript:`
* `file:`
* `ftp:`
* cross-origin URLs unless global scanner scope explicitly allows them
* malformed URLs
* URLs that resolve outside the target scope

For inline `data:` source maps, do not decode by default. Create a `candidate` finding with `map_reference_type="inline_data_url"` and `map_fetch_status="not_fetched_inline"`. This keeps the check cheap and avoids storing large source content.

### Common `.map` fallback probing

For each fetched JavaScript or CSS asset, also test one common fallback URL if no explicit source map reference was found:

* asset URL + `.map`

Examples:

* `/static/app.min.js` -> `/static/app.min.js.map`
* `/assets/site.css?v=1` -> `/assets/site.css.map` after removing the query string for the fallback path

Do not generate large wordlists. Do not brute force filenames. Do not try parent directories. Do not fetch map URLs from source map `sources`.

### Source map fetch

For each accepted source map URL:

1. Fetch with `GET`.
2. Enforce `max_response_bytes`.
3. Treat status `200` with parseable JSON as accessible.
4. Treat `401` or `403` as protected, not a confirmed exposure.
5. Treat `404`, `410`, DNS failures, and TLS failures as not exposed for that candidate.
6. Treat redirects as valid only if the final URL remains in scope.
7. Parse the body as JSON.

A valid external source map should normally have:

* `version`
* at least one of `sources`, `sections`, or `mappings`

Source Map v3 indicators:

* `version` is `3`
* `file` is a string, optional
* `sources` is a list, optional
* `sourcesContent` is a list, optional
* `names` is a list, optional
* `mappings` is a string, optional
* `sourceRoot` is a string, optional
* `sections` is a list, optional

Do not require all fields. Bundlers vary.

### Classification

Create a confirmed finding when:

* an external `.map` URL is in scope,
* it returns HTTP `200`,
* the body parses as JSON,
* and the parsed JSON looks like a source map.

Confidence rules:

* `high`: explicit `sourceMappingURL` reference points to an accessible valid source map.
* `medium`: fallback `.map` URL is accessible and valid, but no asset reference was found.
* `low`: source map reference exists, but the map is inline, blocked, too large, malformed, or cannot be fetched due to transient errors.

Finding status rules:

* `confirmed`: accessible valid external source map.
* `candidate`: referenced inline map, blocked map, oversized response, malformed map, timeout, or transient network error.
* `rejected`: checked fallback or referenced map returned clear non-exposure status such as `404` or `410`.
* `stale`: a previously confirmed map is no longer accessible in a later run.

### Extracted deterministic attributes

Extract only metadata needed for later scanner work:

* asset URL
* map URL
* map reference type:

  * `comment`
  * `fallback`
  * `inline_data_url`
* asset kind:

  * `javascript`
  * `css`
  * `unknown`
* map status code
* source map version
* number of `sources`
* number of `sourcesContent` entries
* whether `sourcesContent` is present
* whether `sourceRoot` is present
* whether `sections` is present
* sample source paths, bounded
* source path categories:

  * `webpack`
  * `vite`
  * `nextjs`
  * `angular`
  * `react`
  * `vue`
  * `svelte`
  * `node_modules`
  * `absolute_path`
  * `relative_path`
  * `url`
  * `unknown`
* obvious internal path indicators:

  * `/src/`
  * `/app/`
  * `/components/`
  * `/pages/`
  * `/routes/`
  * `/server/`
  * `/api/`
  * Windows drive path such as `C:\`
  * Unix home or build paths such as `/home/`, `/Users/`, `/builds/`

Do not run semantic source analysis in this check. Do not infer vulnerabilities from source code here. Later checks may use the metadata and evidence IDs.

### Secret and PII handling

The runner may detect obvious secret-like strings inside source map metadata or bounded source snippets only if the project already has a shared deterministic secret detector. If that detector exists, this check may set:

* `contains_secret_indicators=true`
* `secret_indicator_count`
* `secret_evidence_ids`

Do not persist raw secrets. Store redacted evidence according to shared evidence rules.

If no shared detector exists, do not add ad-hoc secret scanning here.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Persist one `Evidence` record for each important HTTP response:

* fetched JavaScript or CSS asset that contains an explicit source map reference
* fetched external source map response
* blocked or oversized source map response when useful for audit
* rejected candidate only when the project keeps negative evidence, otherwise keep it in runner diagnostics

For valid source maps, store a bounded excerpt or normalized metadata. Do not store full `sourcesContent` by default.

### `SourceMapSignature`

```json
{
  "id": "uuid",
  "target_id": "ScanTarget.id",
  "asset_url": "https://example.test/static/app.js",
  "asset_final_url": "https://example.test/static/app.js",
  "asset_kind": "javascript | css | unknown",
  "map_url": "https://example.test/static/app.js.map",
  "map_final_url": "https://example.test/static/app.js.map",
  "map_reference_type": "comment | fallback | inline_data_url",
  "source_mapping_url_raw": "app.js.map",
  "http_status": 200,
  "content_type": "application/json",
  "source_map_version": 3,
  "sources_count": 42,
  "sources_content_count": 42,
  "has_sources_content": true,
  "has_source_root": false,
  "has_sections": false,
  "source_path_samples": [
    "webpack://app/src/main.ts",
    "webpack://app/src/components/Login.tsx"
  ],
  "source_path_categories": [
    "webpack",
    "react",
    "node_modules"
  ],
  "internal_path_indicators": [
    "/src/",
    "/components/"
  ],
  "contains_secret_indicators": false,
  "secret_indicator_count": 0,
  "map_body_sha256": "hex-string",
  "asset_evidence_id": "Evidence.id",
  "map_evidence_id": "Evidence.id",
  "first_seen_at": "ISO-8601",
  "last_seen_at": "ISO-8601"
}
```

### `SourceMapFinding`

```json
{
  "id": "uuid",
  "target_id": "ScanTarget.id",
  "signature_id": "SourceMapSignature.id",
  "title": "Public source map exposed",
  "status": "candidate | confirmed | rejected | stale",
  "confidence": "low | medium | high",
  "severity": "info | low | medium",
  "asset_url": "https://example.test/static/app.js",
  "map_url": "https://example.test/static/app.js.map",
  "summary": "A public JavaScript or CSS source map was found for a frontend asset.",
  "impact_notes": [
    "May expose original source paths, comments, route names, framework structure, or embedded source content."
  ],
  "evidence_ids": [
    "Evidence.id"
  ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### Severity guidance

Default severity is `info`.

Raise to `low` when an accessible valid source map contains `sourcesContent` or clear internal source paths.

Raise to `medium` only when a shared deterministic secret detector flags redacted secret indicators in source map content or metadata. Do not raise to `medium` based on source map exposure alone.

The final severity decision remains application-owned and must follow the shared severity policy.

### Idempotency

Use a stable uniqueness key:

* `target_id`
* normalized `asset_url`
* normalized `map_url`
* `map_reference_type`

Update `last_seen_at`, status, evidence IDs, hash, and extracted counts on repeat runs. Do not create duplicate findings for the same asset-map pair.

## Safety

This check is read-only.

Allowed methods:

* `GET`
* `HEAD` only if the project already uses it for safe preflight checks

Disallowed behavior:

* no `POST`, `PUT`, `PATCH`, or `DELETE`
* no form submission
* no login attempts
* no credential use by default
* no source map `sources` fetching
* no source code execution
* no JavaScript execution in a browser
* no brute-force filename discovery
* no cross-origin fetching unless global scanner scope allows it
* no persistence of full `sourcesContent` unless explicitly enabled by project policy
* no raw secret persistence

Payload restrictions:

* request bodies are empty
* query strings come only from discovered asset references or direct `.map` fallback
* do not add scanner-generated attack payloads

PII handling:

* Treat source map contents as potentially sensitive.
* Store hashes, counts, bounded samples, and redacted snippets.
* Do not persist full source files from `sourcesContent` by default.
* If `sourcesContent` is stored under an explicit debug setting, it must go to the secure evidence store and follow retention policy.

AI involvement: `None`.

No deterministic gap requires AI. The check parses HTTP responses, source map comments, JSON shape, and bounded metadata.

## Pass/fail check

### Positive assertions

A run passes when all of these are true:

* Given an HTML page that references `/static/app.js`, and `/static/app.js` contains `//# sourceMappingURL=app.js.map`, the runner requests `/static/app.js.map`.
* Given `/static/app.js.map` returns HTTP `200` with valid Source Map v3 JSON, the runner creates one `SourceMapFinding` with:

  * `status="confirmed"`
  * `confidence="high"`
  * `map_reference_type="comment"`
  * at least one `Evidence.id`
* Given no explicit source map comment exists but `/static/app.js.map` exists and parses as a source map, the runner creates one confirmed finding with `confidence="medium"` and `map_reference_type="fallback"`.
* Given an inline `data:` source map comment, the runner creates a candidate finding or diagnostic with `map_reference_type="inline_data_url"` and does not decode or persist the full inline map by default.
* Given a valid map with `sourcesContent`, the runner sets `has_sources_content=true` and records `sources_content_count`.
* Given a valid map with source paths such as `webpack://app/src/Login.tsx`, the runner stores bounded `source_path_samples` and classifies path categories deterministically.
* Given a previously confirmed source map later returns `404`, the runner updates the finding to `stale` or creates a rejected observation according to the project’s existing lifecycle rules.
* Given repeated runs against the same target and same map URL, the runner updates the existing record instead of creating duplicates.

### Negative assertions

The runner must not:

* modify the protected YAML frontmatter or shared schema files
* hard-code expected technologies for a hostname
* create a confirmed finding for a `.map` response that is not parseable JSON
* create a confirmed finding for a JSON response that does not look like a source map
* fetch URLs listed inside the source map `sources` array
* fetch cross-origin source map URLs unless global scope explicitly allows them
* decode and store inline `data:` source maps by default
* persist full `sourcesContent` by default
* persist raw secrets
* execute JavaScript or CSS
* submit forms or authenticate
* retry indefinitely after timeouts or TLS errors
* scan unbounded asset lists
* generate source map wordlists beyond the single `.map` fallback per known asset
* use AI to classify findings
* mark blocked `401` or `403` source maps as confirmed exposure
* treat a redirect to an out-of-scope host as valid

## Test fixtures

Primary fixture: `juice-shop`.

Use a small static fixture app or fixture route if Juice Shop does not expose source maps reliably in the selected container image.

Recommended fixture slug: `source-map-fixture`.

Fixture behavior:

* Serves `/` with:

  * `<script src="/static/app.min.js"></script>`
  * `<link rel="stylesheet" href="/static/app.css">`
* Serves `/static/app.min.js` with a trailing source map comment:

  * `//# sourceMappingURL=app.min.js.map`
* Serves `/static/app.min.js.map` as valid Source Map v3 JSON with:

  * `version: 3`
  * `sources`
  * `sourcesContent`
  * `mappings`
* Serves `/static/app.css` with a CSS source map comment:

  * `/*# sourceMappingURL=app.css.map */`
* Serves `/static/app.css.map` as valid Source Map v3 JSON.
* Serves `/static/no-comment.js` with no source map comment.
* Serves `/static/no-comment.js.map` as valid Source Map v3 JSON to test fallback.
* Serves `/static/bad.js` with `//# sourceMappingURL=bad.js.map`.
* Serves `/static/bad.js.map` as non-JSON to test rejection.
* Serves `/static/protected.js` with `//# sourceMappingURL=protected.js.map`.
* Serves `/static/protected.js.map` as `403` to test candidate/protected handling.
* Serves `/static/inline.js` with an inline `data:` source map to test non-decoding behavior.

Minimum fixture source map body:

```json
{
  "version": 3,
  "file": "app.min.js",
  "sources": [
    "webpack://source-map-fixture/src/main.ts",
    "webpack://source-map-fixture/src/components/Login.tsx"
  ],
  "sourcesContent": [
    "console.log('fixture main');",
    "export function Login() { return null; }"
  ],
  "names": [],
  "mappings": ""
}
```

DVWA and WebGoat are optional negative fixtures. They may be used to confirm the runner handles normal pages without source maps and does not create false positives.

## Acceptance criteria

The implementation is acceptable when:

* It is deterministic and uses no AI.
* It uses shared `ScanTarget` and `Evidence`.
* It defines only `SourceMapSignature` and `SourceMapFinding` as stub-specific types.
* It fetches only bounded same-origin JavaScript, CSS, and source map candidates.
* It detects explicit `sourceMappingURL` comments in JavaScript and CSS.
* It performs only one `.map` fallback probe per known asset.
* It parses valid Source Map v3 JSON without requiring every optional field.
* It stores bounded metadata, hashes, and evidence references.
* It does not persist full `sourcesContent` by default.
* It handles inline `data:` source maps without decoding them by default.
* It handles `401`, `403`, `404`, malformed JSON, oversized responses, redirects, TLS errors, and timeouts without crashing.
* It respects global scanner scope and does not follow cross-origin map references by default.
* It is idempotent across repeated runs.
* It completes within the configured request, asset, response-size, and map-fetch budgets.
* It has unit tests for parser behavior, URL resolution, source map validation, classification, persistence keys, and safety limits.
* It has fixture tests covering confirmed, fallback, inline, protected, malformed, stale, and negative cases.
* It emits clear diagnostics for skipped candidates without turning skips into confirmed findings.

