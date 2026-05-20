---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 1
spec: 3
slug: frontend-framework
status: done        # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 1.3 Frontend framework

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

Detect frontend frameworks, meta-frameworks, and major client-side libraries from HTTP response evidence. The runner uses this to choose later checks, avoid irrelevant probes, explain attack surface, and group findings by technology. Detection must be based on observable evidence such as HTML, headers, linked assets, and static bundle contents, never on the target hostname.

## Inputs

The runner receives a shared `ScanTarget` from `../00-shared-schema.md`.

Required input:

* `ScanTarget.base_url`
* `ScanTarget.host`

Optional input:

* scan ID or run ID, if the project already uses one
* existing shared `Evidence` records from earlier phase-1 probes
* HTTP client configuration from the scanner
* TLS policy from the scanner
* redirect policy from the scanner
* optional cookies or credentials only when the active RoE profile allows authenticated browsing

Config knobs:

```json
{
  "request_timeout_seconds": 10,
  "max_redirects": 5,
  "same_origin_only": true,
  "fetch_linked_assets": true,
  "max_linked_assets": 12,
  "max_asset_bytes": 262144,
  "max_body_bytes": 524288,
  "store_match_context_bytes": 160,
  "allow_external_asset_fetch": false,
  "allow_source_map_fetch": false,
  "user_agent": "scanner-default"
}
```

Rules:

* Default mode is unauthenticated and read-only.
* Fetch only the base page and same-origin assets referenced by that page.
* Do not crawl the whole site.
* Do not execute JavaScript.
* Do not submit forms.
* Do not infer a framework from hostname, page title, favicon, visual style, or generic path names alone.

## Detection logic

### 1. Collect base response evidence

Send a `GET` request to `ScanTarget.base_url`.

Record shared `Evidence` for:

* final URL after allowed redirects
* HTTP status
* response headers
* content type
* response body snippet or normalized body hash
* TLS or connection error, if any

Only parse the body when content type is compatible with text, HTML, JavaScript, JSON, or CSS.

If the first response is not HTML but is text-compatible, still scan it for deterministic markers. If the response is binary, do not scan the body.

### 2. Extract same-origin asset references

From HTML responses, extract:

* `<script src="...">`
* `<link rel="modulepreload" href="...">`
* `<link rel="preload" as="script" href="...">`
* `<link rel="stylesheet" href="...">`

Normalize URLs against the final base URL.

Fetch an asset only when all conditions are true:

* `fetch_linked_assets=true`
* URL is same-origin, unless `allow_external_asset_fetch=true`
* scheme is `http` or `https`
* asset count is within `max_linked_assets`
* response body is within `max_asset_bytes`
* method is `GET`

Do not fetch source maps by default. Files ending in `.map` may expose source code and must be skipped unless `allow_source_map_fetch=true`.

Record each fetched asset as shared `Evidence`.

### 3. Normalize evidence before matching

For each text-compatible response:

* decode as UTF-8 with replacement for invalid bytes
* preserve original content hash
* scan only up to configured byte limits
* strip null bytes
* keep enough context around matches for audit
* do not log full bodies unless the shared evidence store already supports safe payload storage

The matcher works on normalized text and URL paths.

### 4. Match deterministic signatures

Use a registry of deterministic signatures. Each signature has:

* technology name
* category
* marker pattern
* source type
* confidence contribution
* version extraction rule, if safe
* false-positive notes

Supported categories:

* `framework`
* `meta_framework`
* `library`
* `css_framework`
* `unknown`

Initial signatures:

| Technology   |         Category | Evidence marker                                                               | Confidence |
| ------------ | ---------------: | ----------------------------------------------------------------------------- | ---------: |
| Angular      |      `framework` | `ng-version=` in HTML                                                         |       high |
| Angular      |      `framework` | `_ngcontent-` or `_nghost-` plus Angular bundle marker                        |     medium |
| AngularJS    |      `framework` | `ng-app`, `ng-controller`, or `angular.js` script path                        |     medium |
| React        |      `framework` | `data-reactroot` or `react-dom` in same-origin JS                             |     medium |
| React        |      `framework` | `__REACT_DEVTOOLS_GLOBAL_HOOK__` in JS                                        |        low |
| Vue          |      `framework` | `data-v-` scoped attributes plus Vue bundle marker                            |     medium |
| Vue          |      `framework` | `vue.runtime`, `createApp(` with Vue import marker, or `__VUE__`              |     medium |
| Svelte       |      `framework` | `data-svelte-h`                                                               |       high |
| SvelteKit    | `meta_framework` | `__SVELTEKIT_DATA__` or `/_app/immutable/`                                    |       high |
| Next.js      | `meta_framework` | `__NEXT_DATA__`                                                               |       high |
| Next.js      | `meta_framework` | `/_next/static/` asset path                                                   |       high |
| Nuxt         | `meta_framework` | `__NUXT__`, `window.__NUXT__`, or `/_nuxt/`                                   |       high |
| Gatsby       | `meta_framework` | `___gatsby`, `gatsby-focus-wrapper`, or `/page-data/`                         |       high |
| Astro        | `meta_framework` | `astro-island`, `astro-slot`, or `data-astro-cid`                             |       high |
| Remix        | `meta_framework` | `__remixContext` or `@remix-run` in same-origin JS                            |       high |
| HTMX         |        `library` | `hx-get`, `hx-post`, `hx-target`, or `htmx.org` script marker                 |     medium |
| Alpine.js    |        `library` | `x-data` plus Alpine script marker                                            |     medium |
| Stimulus     |        `library` | `data-controller` plus Stimulus or Hotwire marker                             |     medium |
| Turbo        |        `library` | `<turbo-frame`, `data-turbo`, or Hotwire Turbo marker                         |     medium |
| jQuery       |        `library` | `jquery.js`, `jquery.min.js`, or `jQuery.fn.jquery`                           |     medium |
| Bootstrap    |  `css_framework` | `bootstrap.css`, `bootstrap.min.css`, `bootstrap.bundle.js`                   |     medium |
| Tailwind CSS |  `css_framework` | Tailwind-generated utility density plus Tailwind marker in CSS or config leak |        low |
| Material UI  |        `library` | deterministic `Mui` class family plus React evidence                          |     medium |

Weak markers must not produce confirmed findings on their own.

Weak examples:

* `<div id="app">`
* `<div id="root">`
* generic `main.js`
* generic `bundle.js`
* generic `static/js/`
* page text saying “React”, “Vue”, or “Angular” without technical evidence
* CSS class names that could be hand-written
* CDN URL comments without a loaded asset or script tag

### 5. Version extraction

Extract versions only when directly visible in evidence.

Allowed examples:

* `ng-version="16.2.0"`
* `/jquery-3.7.1.min.js`
* `/bootstrap/5.3.3/bootstrap.min.css`
* package banner comment inside fetched same-origin JS or CSS

Do not guess versions from chunk hashes, release dates, filenames without version numbers, or framework defaults.

Version confidence is separate from framework confidence.

### 6. Confidence and status

Confidence values:

* `high`: unique deterministic marker exists, such as `__NEXT_DATA__`, `/_next/static/`, `ng-version`, `/_nuxt/`, `astro-island`, `___gatsby`, or `__SVELTEKIT_DATA__`
* `medium`: two or more compatible markers exist, or one direct package marker exists in fetched same-origin asset content
* `low`: one weak but plausible marker exists and no conflicting evidence exists

Status values:

* `confirmed`: confidence is `high`, or confidence is `medium` with at least two evidence points
* `candidate`: confidence is `low`, or confidence is `medium` with only one evidence point
* `rejected`: a candidate was evaluated and not supported by evidence
* `stale`: a previous finding for this target was not observed in the current scan

Conflict rules:

* A site may use more than one technology.
* A meta-framework may imply a base framework only when the relationship is deterministic.

  * Next.js may produce a React finding with `relationship="implied_by_nextjs"`.
  * Nuxt may produce a Vue finding with `relationship="implied_by_nuxt"`.
  * SvelteKit may produce a Svelte finding with `relationship="implied_by_sveltekit"`.
* Do not reject React just because Next.js was found.
* Do not reject Vue just because Nuxt was found.
* Do not report a base framework as `confirmed` from a meta-framework unless the implication rule is explicit.

## Persistence

Use shared `ScanTarget` and shared `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define these stub-specific types.

### `FrontendFrameworkSignature`

A deterministic rule used by the matcher.

```json
{
  "id": "string",
  "technology": "string",
  "category": "framework | meta_framework | library | css_framework | unknown",
  "pattern_type": "literal | regex | path_prefix | header",
  "pattern": "string",
  "source_types": ["html", "javascript", "css", "header", "url_path"],
  "confidence": "low | medium | high",
  "version_regex": "string | null",
  "requires_any": ["signature_id"],
  "requires_all": ["signature_id"],
  "false_positive_notes": "string"
}
```

Implementation notes:

* `id` must be stable.
* Regex signatures must be reviewed and bounded.
* Regex matching must not allow catastrophic backtracking.
* `requires_any` and `requires_all` refer to other signature IDs.
* Signature registry changes should be versioned if the project already versions detector rules.

### `FrontendFrameworkFinding`

A persisted result for one detected technology on one target.

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "scan_id": "uuid | null",
  "technology": "string",
  "category": "framework | meta_framework | library | css_framework | unknown",
  "version": "string | null",
  "version_confidence": "low | medium | high | null",
  "confidence": "low | medium | high",
  "status": "candidate | confirmed | rejected | stale",
  "relationship": "direct | implied_by_nextjs | implied_by_nuxt | implied_by_sveltekit | related_asset | null",
  "matched_signature_ids": ["string"],
  "evidence_ids": ["uuid"],
  "observed_locations": [
    {
      "evidence_id": "uuid",
      "source_type": "html | javascript | css | header | url_path",
      "url": "string | null",
      "header_name": "string | null",
      "match_context": "string"
    }
  ],
  "first_seen_at": "ISO-8601",
  "last_seen_at": "ISO-8601",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

Persistence rules:

* Store raw HTTP bodies only through shared `Evidence`, not inside `FrontendFrameworkFinding`.
* `evidence_ids` must point to the exact evidence used for the finding.
* `match_context` must be short and redacted.
* Re-running the detector for the same scan must not create duplicate findings.
* If a previous technology is not found in the current scan, mark the old finding `stale` rather than deleting it.
* If evidence changes from `candidate` to `confirmed`, update the existing finding.
* If evidence is later disproven, mark it `rejected` and keep the evidence trail.

## Safety

This probe is read-only.

Allowed HTTP methods:

* `GET`
* `HEAD` only if the shared HTTP client already uses it for metadata

Blocked HTTP methods:

* `POST`
* `PUT`
* `PATCH`
* `DELETE`
* `OPTIONS` unless the shared scanner has a dedicated safe capability probe for it

Payload rules:

* Do not send request bodies.
* Do not submit forms.
* Do not click links.
* Do not execute JavaScript.
* Do not run browser automation for this spec.
* Do not fetch external assets by default.
* Do not fetch source maps by default.
* Do not crawl beyond the base page and configured linked assets.
* Do not use credentials unless RoE explicitly allows authenticated browsing.
* Do not bypass TLS policy.
* Do not change cookies, headers, or auth state except the scanner’s normal user agent and accepted safe headers.

PII and secret handling:

* Treat response bodies, scripts, comments, and headers as untrusted evidence.
* Redact obvious secrets before storing match context.
* Do not store cookies, authorization headers, CSRF tokens, session IDs, or API keys in finding records.
* If a marker appears next to sensitive data, store only the marker and a hash-backed evidence reference.

AI involvement:

* `None`.
* Detection is deterministic.
* No LLM is needed for matching, confidence, status, version extraction, or persistence.
* Target content may contain prompt-injection text. It must be treated as evidence only, never as instructions. 

Deterministic gap:

* None for MVP.
* Unknown frameworks should be reported as no finding unless a deterministic signature is added.

## Pass/fail check

A run passes when all assertions below are true.

### Positive assertions

* Given an HTML response containing `ng-version="..."`, the runner creates an Angular `FrontendFrameworkFinding`.
* Given an HTML response containing `__NEXT_DATA__`, the runner creates a Next.js `FrontendFrameworkFinding` with `confidence="high"` and `status="confirmed"`.
* Given an HTML response referencing `/_nuxt/` same-origin assets, the runner creates a Nuxt finding with `confidence="high"` and `status="confirmed"`.
* Given an HTML response containing `astro-island`, the runner creates an Astro finding with `confidence="high"` and `status="confirmed"`.
* Given an HTML response containing `data-svelte-h`, the runner creates a Svelte finding with `confidence="high"` and `status="confirmed"`.
* Given a same-origin script path `/jquery-3.7.1.min.js`, the runner creates a jQuery finding and extracts version `3.7.1`.
* Given a same-origin CSS path containing `bootstrap.min.css`, the runner creates a Bootstrap finding.
* Given existing shared `Evidence` records from the same scan, the runner may reuse them instead of refetching the same URL.
* Every finding has at least one `evidence_id`.
* Every `matched_signature_ids` entry refers to a known `FrontendFrameworkSignature`.
* Every confirmed finding has `confidence="medium"` or `confidence="high"`.
* If a previous finding is not seen in the current scan, it is marked `stale`.

### Negative assertions

* The runner must not infer technology from hostname.
* The runner must not hard-code fixture hostname to expected technology.
* The runner must not report React from `<div id="root"></div>` alone.
* The runner must not report Vue from `<div id="app"></div>` alone.
* The runner must not report Angular from a generic `main.js` filename alone.
* The runner must not report Tailwind from one utility-looking class alone.
* The runner must not fetch external CDN assets unless `allow_external_asset_fetch=true`.
* The runner must not fetch source maps unless `allow_source_map_fetch=true`.
* The runner must not execute JavaScript.
* The runner must not submit forms.
* The runner must not send authenticated requests unless the RoE profile allows it.
* The runner must not store raw cookies, authorization headers, CSRF tokens, or API keys inside `FrontendFrameworkFinding`.
* The runner must not create duplicate findings for the same target, scan, and technology.
* The runner must not mark a low-confidence single weak marker as `confirmed`.
* The runner must not call an LLM.

### Error handling assertions

* TLS failure creates an error `Evidence` record or scan observation and does not crash the scan.
* Timeout creates a bounded failure result and does not retry forever.
* Non-HTML responses do not crash parsing.
* Malformed HTML does not crash parsing.
* Oversized assets are truncated or skipped according to config.
* Redirect loops stop at `max_redirects`.

## Test fixtures

Use existing fixtures where possible, but keep assertions evidence-based.

### `juice-shop`

Use for Angular detection.

Expected evidence examples:

* `ng-version`
* Angular-specific DOM attributes
* same-origin Angular bundle markers

Assertions:

* Angular is detected from response evidence.
* Confidence is `high` when `ng-version` exists.
* Status is `confirmed`.
* The runner must not detect React, Vue, Next.js, Nuxt, Gatsby, Astro, or Svelte unless matching evidence exists.

### `dvwa`

Use as a mostly server-rendered PHP app with possible frontend libraries.

Expected behavior:

* Do not detect Angular, React, Vue, Next.js, Nuxt, Gatsby, Astro, or Svelte without evidence.
* Detect jQuery or Bootstrap only if deterministic script or CSS evidence exists.
* Do not treat PHP, Apache, Nginx, or server headers as frontend framework findings.

### `webgoat`

Use as a negative or mixed frontend fixture.

Expected behavior:

* Do not detect modern frontend frameworks unless deterministic markers exist.
* If JavaScript libraries are present, report only those supported by deterministic signatures.

### `frontend-framework-static`

Add a small local fixture if existing apps do not cover all markers.

It should expose static pages:

* `/angular.html` with `ng-version`
* `/next.html` with `__NEXT_DATA__`
* `/nuxt.html` with `/_nuxt/`
* `/sveltekit.html` with `__SVELTEKIT_DATA__`
* `/astro.html` with `astro-island`
* `/gatsby.html` with `___gatsby`
* `/react-weak.html` with only `<div id="root"></div>`
* `/vue-weak.html` with only `<div id="app"></div>`
* `/jquery-version.html` with `/jquery-3.7.1.min.js`
* `/bootstrap.html` with `/bootstrap.min.css`
* `/hostile.html` with prompt-injection text inside HTML comments

The hostile fixture must not affect detection logic. Its content is evidence only.

## Acceptance criteria

The implementation is acceptable when:

* It is deterministic and uses no AI.
* It uses shared `ScanTarget` and shared `Evidence`.
* It defines only `FrontendFrameworkSignature` and `FrontendFrameworkFinding` as stub-specific types.
* It performs only read-only HTTP requests.
* It never executes JavaScript.
* It does not crawl beyond the configured base page and linked asset budget.
* It detects supported frontend technologies from direct evidence.
* It records exact evidence IDs for every finding.
* It distinguishes `candidate`, `confirmed`, `rejected`, and `stale`.
* It uses only `low`, `medium`, and `high` confidence.
* It extracts versions only from direct evidence.
* It handles TLS errors, timeouts, malformed HTML, non-HTML responses, redirects, and oversized assets without crashing.
* It does not hard-code hostname to expected technology.
* It has negative tests for weak markers.
* It has fixture tests for at least Angular, Next.js, Nuxt, Astro, SvelteKit, jQuery, Bootstrap, and weak false-positive cases.
* It is idempotent across repeated runs for the same target and scan.
* It completes within the configured request and asset budget.
* It has no flaky retries.
* It does not store secrets or full sensitive payloads in finding records.

