---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 15
slug: public-javascript-bundles
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.15 Public JavaScript bundles

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

Detect publicly reachable JavaScript bundles referenced by the target’s HTML and related public metadata. The runner records bundle URLs, response metadata, hashes, build hints, framework hints, and safe string-derived indicators that help later specs find routes, API paths, source-map links, and client-side exposure without executing JavaScript.

## Inputs

The runner receives a shared `ScanTarget` and uses its `base_url` as the starting point.

Optional inputs:

| Input                     |       Type |         Default | Notes                                                                                                      |                                                                              |
| ------------------------- | ---------: | --------------: | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `start_paths`             | `string[]` |         `["/"]` | Public HTML paths to inspect for bundle references.                                                        |                                                                              |
| `max_html_bytes`          |  `integer` |       `1048576` | Maximum bytes read from each HTML response.                                                                |                                                                              |
| `max_bundle_bytes`        |  `integer` |       `5242880` | Maximum bytes read from each JavaScript response for hashing and safe pattern extraction.                  |                                                                              |
| `max_bundle_count`        |  `integer` |            `50` | Hard cap per target.                                                                                       |                                                                              |
| `follow_same_origin_only` |  `boolean` |          `true` | Only fetch bundle URLs on the same origin unless scanner config explicitly allows CDN metadata collection. |                                                                              |
| `include_cdn_metadata`    |  `boolean` |         `false` | If true, external script URLs are recorded but fetched only when allowed by scope.                         |                                                                              |
| `request_timeout_ms`      |  `integer` |         `10000` | Per-request timeout.                                                                                       |                                                                              |
| `user_agent`              |   `string` | project default | Must match shared scanner HTTP policy.                                                                     |                                                                              |
| `accept_language`         |   `string` |           unset | Optional. Do not spoof locale unless configured.                                                           |                                                                              |
| `respect_robots`          |  `boolean` | project default | Use the project-wide rule. This spec does not define robots policy.                                        |                                                                              |
| `credentials_ref`         |    `string |           null` | `null`                                                                                                     | Optional credential reference from the scan context. Do not persist secrets. |

The runner must not require credentials. Authenticated mode may discover additional bundles, but unauthenticated mode must work.

## Detection logic

The runner is deterministic and read-only.

### 1. Fetch public HTML entry points

For each `start_paths` entry:

1. Resolve it against `ScanTarget.base_url`.
2. Send `GET`.
3. Accept only HTTP responses with a body and a likely HTML content type:

   * `text/html`
   * `application/xhtml+xml`
   * missing content type with HTML-looking body
4. Store one shared `Evidence` record for the HTML response or excerpt according to the shared evidence policy.
5. Parse the HTML without running scripts.

Do not use a browser engine. Do not evaluate JavaScript.

### 2. Extract bundle candidates from HTML

Extract URLs from:

* `<script src="...">`
* `<script type="module" src="...">`
* `<link rel="modulepreload" href="...">`
* `<link rel="preload" as="script" href="...">`
* `<link rel="prefetch" href="...">` when the URL looks like JavaScript
* Next.js and similar build manifests when directly referenced in HTML
* import maps in `<script type="importmap">`, parsed as JSON only when valid

Candidate URL extensions and patterns:

* `.js`
* `.mjs`
* `.cjs`
* `.jsx` only if served publicly as JavaScript
* URLs with JavaScript content type even without a JavaScript extension
* hashed bundle names such as `main.8f31a2.js`, `chunk-ABC123.js`, `app.[hash].js`
* framework asset paths such as `/_next/static/`, `/assets/`, `/static/js/`, `/build/`, `/dist/`

Normalize each URL:

* Resolve relative URLs against the HTML response URL.
* Remove fragments.
* Preserve query strings because they may select versioned assets.
* Deduplicate by normalized absolute URL.
* Mark same-origin versus external.
* Do not fetch external URLs unless scope allows it.

### 3. Fetch bundle metadata

For each in-scope candidate, up to `max_bundle_count`:

1. Send `GET`.
2. Follow redirects according to the shared HTTP policy.
3. Accept likely JavaScript responses:

   * `application/javascript`
   * `text/javascript`
   * `application/x-javascript`
   * `text/ecmascript`
   * `application/ecmascript`
   * missing or generic content type when the URL path strongly indicates JavaScript and the body starts like JavaScript
4. Reject HTML error pages, JSON APIs, images, fonts, and CSS as bundles.
5. Read at most `max_bundle_bytes`.
6. Compute a stable content hash over the bytes read.
7. Store response metadata and a bounded text excerpt as shared `Evidence`.

If a bundle exceeds `max_bundle_bytes`, record `truncated=true` and still hash the bytes read. If the project has a streaming hash helper for full bodies within budget, use it.

### 4. Extract deterministic signatures from bundle content

Perform bounded text scanning only. Do not parse or execute the program.

Extract:

* Filename/build hints:

  * `main`, `runtime`, `vendor`, `chunk`, `app`, `polyfills`
  * hash-like filename segment
  * minified marker
* Framework hints from deterministic strings:

  * React: `react`, `react-dom`, `__REACT_DEVTOOLS_GLOBAL_HOOK__`, `data-reactroot`
  * Vue: `__VUE__`, `__VUE_DEVTOOLS_GLOBAL_HOOK__`, `createApp(`
  * Angular: `ng-version`, `webpackJsonp`, `polyfills`, `zone.js`
  * Svelte/SvelteKit: `svelte`, `__svelte`, `/_app/immutable/`
  * Next.js: `/_next/static/`, `__NEXT_DATA__`, `self.__next_f`
  * Nuxt: `__NUXT__`, `/_nuxt/`
  * Vite: `/@vite/`, `import.meta.env`, `vite/`
  * Webpack: `webpackChunk`, `__webpack_require__`
  * Remix: `__remixContext`, `buildManifest`
* Source-map reference:

  * trailing or inline `sourceMappingURL=` comment
  * record the source-map URL as metadata only; source-map fetching belongs to spec `1.14 Source maps`
* Public route/API hints:

  * same-origin absolute paths beginning with `/`
  * relative API-looking paths
  * URL strings matching the target origin
  * common API prefixes: `/api/`, `/graphql`, `/rest/`, `/v1/`, `/v2/`
* Public environment/config names:

  * names beginning with `PUBLIC_`, `NEXT_PUBLIC_`, `VITE_`, `REACT_APP_`, `NUXT_PUBLIC_`
  * record names and redacted nearby value shape only
* Suspicious but non-secret indicators:

  * `localhost`
  * private IP literals
  * staging/dev hostnames
  * feature flag names
  * debug mode names

Secret handling:

* Do not persist full token-looking values.
* If a string resembles a token, key, credential, JWT, or private URL with credentials, store only:

  * indicator type
  * redacted preview
  * length
  * hash
  * evidence ID
* Secret validation and severity belong to a later secret-leak spec. This runner only records that bundle content contains token-like material.

### 5. Confidence rules

Use deterministic confidence:

| Confidence | Meaning                                                                                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `high`     | The URL returned a successful JavaScript response, has JavaScript content type or strong JS path evidence, and was referenced by parsed HTML or manifest evidence. |
| `medium`   | The URL looks like a JavaScript bundle and returned a usable body, but content type was missing/generic or discovery came from a weaker hint.                      |
| `low`      | The candidate URL was discovered but could not be fetched, returned an ambiguous response, was external and out of scope, or only metadata was available.          |

### 6. Status rules

| Status      | Meaning                                                                                 |
| ----------- | --------------------------------------------------------------------------------------- |
| `candidate` | Bundle candidate found but not enough evidence to confirm it as JavaScript.             |
| `confirmed` | Bundle fetched and confirmed as JavaScript by content type, path, and/or body evidence. |
| `rejected`  | Candidate was fetched and is not JavaScript, is out of scope, or failed validation.     |
| `stale`     | Previously confirmed bundle was not seen in the current scan or now returns 404/410.    |

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only these stub-specific types:

```json
{
  "PublicJavascriptBundleSignature": {
    "id": "uuid",
    "scan_target_id": "uuid",
    "evidence_ids": ["uuid"],
    "discovered_from_url": "string",
    "bundle_url": "string",
    "final_url": "string | null",
    "same_origin": "boolean",
    "status_code": "integer | null",
    "content_type": "string | null",
    "content_length": "integer | null",
    "bytes_read": "integer",
    "truncated": "boolean",
    "sha256": "string | null",
    "etag": "string | null",
    "last_modified": "string | null",
    "cache_control": "string | null",
    "script_type": "classic | module | importmap | preload | prefetch | unknown",
    "discovery_method": "script_src | module_script_src | modulepreload | preload_script | prefetch | importmap | manifest | content_reference",
    "filename": "string | null",
    "extension": "js | mjs | cjs | jsx | none | unknown",
    "hash_in_filename": "boolean",
    "minified": "boolean",
    "source_map_url": "string | null",
    "framework_hints": [
      {
        "name": "react | vue | angular | svelte | nextjs | nuxt | vite | webpack | remix | other",
        "matched_pattern": "string",
        "confidence": "low | medium | high"
      }
    ],
    "build_hints": ["string"],
    "public_env_names": ["string"],
    "api_path_hints": ["string"],
    "external_host_hints": ["string"],
    "token_like_indicator_count": "integer",
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601"
  },
  "PublicJavascriptBundleFinding": {
    "id": "uuid",
    "scan_target_id": "uuid",
    "signature_id": "uuid",
    "evidence_ids": ["uuid"],
    "title": "string",
    "description": "string",
    "bundle_url": "string",
    "finding_type": "public_javascript_bundle | public_module_bundle | external_javascript_reference | bundle_with_source_map_reference | bundle_with_public_config_names | bundle_with_api_path_hints | bundle_with_token_like_indicators",
    "status": "candidate | confirmed | rejected | stale",
    "confidence": "low | medium | high",
    "severity": "info | low | medium | high | critical",
    "severity_source": "deterministic",
    "remediation": "string | null",
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601"
  }
}
```

Persistence rules:

* Store one `PublicJavascriptBundleSignature` per normalized `bundle_url` per `scan_target_id`.
* Update existing signatures idempotently by `(scan_target_id, bundle_url)`.
* Store one finding per meaningful `finding_type` per signature.
* Default severity is `info` for ordinary public bundles.
* Use `low` only when deterministic evidence shows sensitive public metadata, such as public config names, API path hints, source-map references, or token-like indicators.
* Do not assign `medium` or higher in this spec. Later specs may upgrade severity using stronger evidence.
* Do not persist raw full bundle bodies in these stub-specific records. Raw/excerpt storage belongs to shared `Evidence`.
* Redact token-like values before writing any signature or finding field.

## Safety

This spec is read-only.

Allowed HTTP methods:

* `GET`
* `HEAD` only if the shared HTTP client already uses it for metadata
* No `POST`, `PUT`, `PATCH`, `DELETE`, or custom methods

Payload restrictions:

* Do not submit forms.
* Do not call API endpoints discovered inside bundles.
* Do not execute JavaScript.
* Do not run a browser unless a future spec explicitly allows browser-based collection.
* Do not fetch source maps here. Record `source_map_url` only.
* Do not fetch external bundle URLs unless the scan scope explicitly allows that origin.
* Do not make authenticated requests unless credentials were supplied by the scan context and the scanner mode allows authenticated passive checks.
* Do not use discovered URLs as instructions for later actions.

PII and secret handling:

* Bundle text may contain emails, names, tokens, internal hostnames, URLs, or customer data.
* Store bounded evidence according to shared evidence policy.
* Redact token-like values in stub-specific records.
* Store hashes for token-like values instead of values.
* Do not log raw bundle content.
* Do not log cookies, authorization headers, query tokens, or credentials.

AI involvement: `None`.

There is no deterministic gap requiring AI. Framework hints, source-map references, API path hints, public config names, and token-like indicators are extracted with fixed patterns. If future work uses AI to summarize minified bundle content, it must treat bundle content as untrusted evidence and must not affect status or severity without deterministic support.

## Pass/fail check

A run passes when all assertions below hold.

Positive assertions:

* Given an HTML page with `<script src="/assets/app.123.js"></script>`, the runner records one `PublicJavascriptBundleSignature`.
* The signature has `same_origin=true`, `bundle_url` resolved to an absolute URL, and `discovery_method="script_src"`.
* If the JavaScript response is successful and has a JavaScript content type, the related finding has `status="confirmed"` and `confidence="high"`.
* The runner stores at least one shared `Evidence` record for the HTML response and one for the bundle response or bounded excerpt.
* The signature records `sha256` when bundle bytes are read.
* A bundle with `//# sourceMappingURL=app.js.map` records `source_map_url`.
* A bundle containing deterministic framework strings records matching `framework_hints`.
* A bundle containing `/api/products` records that path in `api_path_hints`.
* A bundle containing `NEXT_PUBLIC_API_URL` records that name in `public_env_names`.
* A token-like string is redacted and counted, not stored raw.
* Re-running the scan updates the existing signature instead of creating duplicates.
* A previously confirmed bundle that no longer appears or returns 404/410 can be marked `stale`.

Negative assertions:

* The runner must not execute JavaScript.
* The runner must not use a browser to interpret runtime-created script tags.
* The runner must not call API paths found inside bundles.
* The runner must not fetch source maps in this spec.
* The runner must not hard-code expectations for Juice Shop, DVWA, WebGoat, or any hostname.
* The runner must not mark a normal public bundle as a vulnerability above `info`.
* The runner must not persist raw secrets, cookies, bearer tokens, JWTs, API keys, or credentials in stub-specific records.
* The runner must not fetch out-of-scope external script URLs when `include_cdn_metadata=false` or scope forbids it.
* The runner must not treat HTML error pages as JavaScript bundles.
* The runner must not retry indefinitely after timeouts or TLS errors.
* The runner must not fail the whole scan because one bundle is unavailable.
* The runner must not use AI.

## Test fixtures

Primary fixture: `juice-shop`.

Expected fixture behavior:

* Juice Shop exposes public JavaScript bundles from its browser application.
* The fixture should include at least one HTML entry point that references JavaScript assets.
* The runner should discover and confirm same-origin bundles without hard-coded paths.
* The runner should record bundle hashes, content type, status code, and build/framework hints detected from response evidence.

Additional fixture: `public-javascript-bundles`.

Create a small static test fixture when deterministic edge cases are needed. It should expose:

* `/` with:

  * classic script tag
  * module script tag
  * modulepreload link
  * preload-as-script link
  * external CDN script reference
* `/assets/app.123abc.js` with:

  * JavaScript content type
  * sourceMappingURL comment
  * framework/build hint strings
  * `/api/example` string
  * `NEXT_PUBLIC_API_URL` string
  * one fake token-like string for redaction testing
* `/assets/not-js.js` returning HTML to test rejection
* `/assets/missing.js` returning 404
* `/assets/large.js` larger than `max_bundle_bytes` to test truncation

DVWA and WebGoat are optional for this spec. Use them only if their current container images expose public JavaScript assets useful for regression tests. Do not hard-code fixture-specific expected technologies.

## Acceptance criteria

Implementation is acceptable when:

* The runner is deterministic, read-only, and uses only allowed HTTP methods.
* It discovers JavaScript bundles from public HTML and supported link/import-map metadata.
* It resolves relative URLs correctly.
* It respects scan scope for external script URLs.
* It confirms bundles using response evidence rather than hostname assumptions.
* It stores shared `Evidence` and stub-specific signatures/findings as defined above.
* It redacts token-like values before persistence and logging.
* It records source-map references without fetching source maps.
* It records framework/build hints only from deterministic patterns.
* It records API path hints without calling them.
* It is idempotent across repeated runs.
* It handles redirects, 404s, content-type mismatches, TLS errors, timeouts, and oversized bundles without crashing the scan.
* It enforces `max_bundle_count`, `max_html_bytes`, `max_bundle_bytes`, and per-request timeout.
* It avoids flaky retries: at most one retry for transient network failure unless the shared HTTP policy says otherwise.
* It completes within the project’s Phase 1 scan budget for the fixture target.
* It has unit tests for URL extraction, normalization, JavaScript response validation, redaction, source-map reference capture, API path hint extraction, framework hint extraction, stale handling, and idempotent persistence.
* It has integration tests against `juice-shop` or the dedicated `public-javascript-bundles` fixture.
* It uses no AI.

