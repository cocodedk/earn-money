---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 15
slug: cached-private-data
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.15 Cached private data

> Phase 3 — Session management · Category: Cross-user session issues

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

Detect authenticated pages or API responses that expose private data through browser, proxy, or back-forward cache behavior after logout. The runner cares because private account data should not remain available to another local user, shared device user, or intermediary cache after the session ends.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar support.
* `scanner_config`: stub-specific knobs listed below.

Required for confirmed testing:

* `test_account`: scoped fixture/test account.
* `login_flow`: known safe login flow.
* `logout_flow`: known logout flow.
* `safe_private_page`: authenticated page or API endpoint that returns a synthetic private marker.

Optional inputs:

* `browser_runner`: project browser automation helper for back-button and bfcache checks.
* `csrf_extractor`: shared helper for login/logout forms with CSRF tokens.
* `private_cache_policy`: configured expected cache directives.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled with scoped credentials. |
| `allow_logout_submission` | `false` | Must be explicitly enabled with known logout flow. |
| `allow_browser_back_cache_check` | `false` | Optional browser automation for back-button/bfcache behavior. |
| `max_private_pages` | `3` | Bounds authenticated pages checked. |
| `max_browser_actions` | `8` | Bounds browser automation steps. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `redact_private_markers` | `true` | Private markers must be redacted or fingerprinted. |

## Detection logic

Detection is deterministic and uses a scoped private marker.

### 1. Authenticate and capture private response

Only run when `allow_login_submission=true` and scoped credentials are available.

1. Create an isolated client or browser context.
2. Log in with the scoped test account.
3. Request `safe_private_page`.
4. Confirm the private marker appears.
5. Record response headers and marker fingerprint.

Do not fetch arbitrary account pages. The private marker must be synthetic or explicitly fixture-safe.

### 2. Evaluate HTTP cache headers

For every private response, inspect:

* `Cache-Control`
* `Pragma`
* `Expires`
* `ETag`
* `Last-Modified`
* `Vary`
* `Surrogate-Control`
* CDN cache headers such as `CF-Cache-Status`, `X-Cache`, `Age`

Expected private response behavior:

* `Cache-Control` includes `no-store`, or an equivalent project-approved private-data policy.
* `private` plus `no-cache` may be acceptable for some API responses, but `no-store` is preferred for sensitive pages.
* Shared-cache indicators should not show private authenticated responses being served from a public cache.

Weak behavior:

* Authenticated private page has `Cache-Control: public`.
* Authenticated private page has a long positive `max-age` without `private` or `no-store`.
* Authenticated private page omits cache controls entirely and contains private marker.
* Private marker appears with CDN/shared-cache hit headers.

### 3. Post-logout access check

Only run when `allow_logout_submission=true` and `logout_flow` is known.

1. Log out from the same isolated client.
2. Re-request `safe_private_page` normally.
3. Confirm the private marker is not returned from the server.

If the private marker is still returned by normal request after logout, classify it under logout invalidation specs first. This spec focuses on cached data, so record the overlap and do not double-count unless the project supports linked findings.

### 4. Optional browser back/bfcache check

Only run when `allow_browser_back_cache_check=true` and a browser runner is available.

1. Log in through the browser.
2. Visit `safe_private_page` and confirm private marker.
3. Log out.
4. Use browser back navigation.
5. Observe whether private marker is visible without a network request or after bfcache restore.
6. Record page lifecycle signals where the browser runner exposes them.

Confirmed cached-private-data behavior:

* Private marker is visible after logout via back button or bfcache.
* Private marker appears while network revalidation is absent or blocked.
* HTTP headers lacked `no-store` and browser restored private page.

### 5. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Private marker is visible after logout through browser back/bfcache. | `confirmed` | `high` |
| Private authenticated response has `Cache-Control: public` or shared-cache hit evidence. | `confirmed` | `high` |
| Private response lacks `no-store` and lacks equivalent private-data cache policy. | `candidate` | `medium` |
| Server still returns private marker after logout on a normal request. | `candidate` | `medium`; link to spec 3.7 |
| Private response uses `no-store` or approved equivalent and marker is not visible after logout. | `rejected` | `high` |
| Test aborted because login, logout, private marker, or browser runner preconditions are missing. | `stale` | `low` |

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `CachedPrivateDataSignature`, `CachedPrivateDataFinding`.

### `CachedPrivateDataSignature`

```ts
export interface CachedPrivateDataSignature {
  signature_id: string;
  private_url: string;
  check_kind:
    | "missing_no_store"
    | "public_cache_control"
    | "shared_cache_hit"
    | "browser_back_cache_restore";
  required_directive?: "no-store" | "private" | "no-cache";
  requires_browser_runner: boolean;
  requires_valid_credentials: true;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `CachedPrivateDataFinding`

```ts
export interface CachedPrivateDataFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  private_url: string;
  logout_url?: string;
  check_kind:
    | "missing_no_store"
    | "public_cache_control"
    | "shared_cache_hit"
    | "browser_back_cache_restore";

  private_marker_fingerprint: string;
  cache_headers: {
    cache_control?: string;
    pragma?: string;
    expires?: string;
    etag_present: boolean;
    last_modified_present: boolean;
    vary?: string;
    age?: string;
    shared_cache_status?: string;
  };

  post_logout_observation: {
    normal_request_private_marker_seen: boolean;
    browser_back_used: boolean;
    browser_back_private_marker_seen: boolean;
    network_revalidation_observed?: boolean;
    bfcache_restore_observed?: boolean;
  };

  title: string;
  summary: string;
  remediation: {
    summary: string;
    steps: string[];
  };

  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";
  safe: false;
  created_at: string;
  updated_at: string;
}
```

Evidence requirements:

* Login request metadata with secrets omitted.
* Private response headers and private marker fingerprint.
* Logout request/response evidence when used.
* Post-logout normal request evidence.
* Optional browser back/bfcache evidence.

Recommended remediation:

* Send `Cache-Control: no-store` on pages and API responses containing sensitive user data.
* Avoid `public` and long `max-age` on authenticated private responses.
* Use `Pragma: no-cache` and conservative `Expires` headers for legacy clients when needed.
* Ensure CDN and reverse-proxy rules bypass or privately cache authenticated responses.
* Clear client-side state on logout, but do not rely on client clearing alone.

## Safety

This check is active because it logs in, visits a private marker page, and may log out.

Allowed:

* One valid login request when `allow_login_submission=true`.
* Requests to configured `safe_private_page` only.
* One known logout request when `allow_logout_submission=true`.
* Optional browser back navigation when explicitly enabled.

Not allowed:

* Password guessing.
* Username guessing.
* Crawling private pages.
* Fetching arbitrary private resources.
* Testing real user accounts not explicitly scoped.
* Extracting private data beyond the synthetic marker.
* Forcing cache poisoning or shared-cache key manipulation.
* Continuing after WAF, abuse detection, lockout, CAPTCHA, MFA challenge, or `429`.

PII and secrets:

* Never log passwords, CSRF tokens, authorization headers, raw cookies, or raw tokens.
* Redact or fingerprint private markers.
* Use fixture-only synthetic markers where possible.
* Do not store screenshots containing real private data.
* Do not send private marker evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Header classification, marker comparison, and browser-state checks are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It requires a scoped account and configured `safe_private_page` for confirmed testing.
* It records cache headers for authenticated private responses.
* It detects `Cache-Control: public` on a private marker response as `confirmed`, `high`.
* It detects shared-cache hit evidence on a private marker response as `confirmed`, `high`.
* It creates a `candidate`, `medium` finding when private marker responses lack `no-store` or approved equivalent.
* It checks normal post-logout access before attributing browser back behavior to caching.
* It performs browser back/bfcache checks only when explicitly enabled.
* It creates a `confirmed`, `high` finding when private marker remains visible after logout via browser back/bfcache.
* It redacts credentials, CSRF tokens, authorization headers, session values, and private markers.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit guessed usernames or passwords.
* It must not crawl private pages.
* It must not fetch arbitrary private resources.
* It must not store screenshots containing real private data.
* It must not run cache poisoning or shared-cache manipulation.
* It must not classify normal server-side post-logout access as only a cache issue.
* It must not use real accounts unless explicitly scoped.
* It must not continue after WAF, abuse detection, lockout, CAPTCHA, MFA challenge, or `429`.
* It must not store raw private markers or tokens in findings.
* It must not send private evidence to an LLM.

## Test fixtures

Use the synthetic fixture slug: `session-cross-user`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/cache/private-public/login` + `/cache/private-public/page` | Private marker response uses `Cache-Control: public, max-age=3600`. | `confirmed`, `high` |
| `/cache/private-missing/login` + `/cache/private-missing/page` | Private marker response lacks cache controls. | `candidate`, `medium` |
| `/cache/private-safe/login` + `/cache/private-safe/page` | Private marker response uses `Cache-Control: no-store`. | `rejected`, `high` or no finding |
| `/cache/shared-hit/login` + `/cache/shared-hit/page` | Private marker response has shared-cache hit header. | `confirmed`, `high` |
| `/cache/back-vulnerable/login` + `/cache/back-vulnerable/logout` + `/cache/back-vulnerable/page` | Browser back shows private marker after logout. | `confirmed`, `high` when browser check enabled |
| `/cache/back-safe/login` + `/cache/back-safe/logout` + `/cache/back-safe/page` | Browser back does not show private marker after logout. | `rejected`, `high` |
| `/cache/logout-invalid/login` + `/cache/logout-invalid/logout` + `/cache/logout-invalid/page` | Normal server request after logout still returns marker. | candidate linked to spec 3.7 |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Private marker: synthetic account-only string
* Account and session store reset between tests

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used for exploratory cache-header observations only.
* Do not make acceptance depend on live apps unless deterministic private-marker fixtures are added.

## Acceptance criteria

The implementation is acceptable when:

* The check is deterministic against the fixture.
* It performs no login unless `allow_login_submission=true`.
* It performs no logout unless `allow_logout_submission=true`.
* It performs no browser back/bfcache check unless `allow_browser_back_cache_check=true`.
* It checks no more than `max_private_pages`.
* It completes within configured request and browser-action budgets.
* It handles missing accounts, missing private marker, missing logout flow, redirects, TLS failures, timeouts, and connection errors gracefully.
* It stops on CAPTCHA, MFA challenge without configured fixture secret, lockout, WAF block, abuse detection, or `429`.
* It redacts credentials, CSRF tokens, authorization headers, session values, and private markers.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `candidate`, `rejected`, and `stale` statuses correctly.
* It defines only `CachedPrivateDataSignature` and `CachedPrivateDataFinding` as stub-specific types.
* Unit tests cover cache-header parsing, private marker fingerprinting, no-store rejection, public cache detection, shared-cache hit detection, post-logout normal request handling, browser-check gating, redaction, safety aborts, and negative assertions.
* Fixture tests cover private-public cache, missing cache controls, safe no-store, shared-cache hit, vulnerable browser back, safe browser back, and logout invalidation overlap.
* AI is not called.
