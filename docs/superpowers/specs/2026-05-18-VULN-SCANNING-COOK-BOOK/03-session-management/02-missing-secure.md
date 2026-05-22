---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 2
slug: missing-secure
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.2 Missing `Secure`

> Phase 3 — Session management · Category: Cookie weaknesses

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

Detect session-bearing cookies that are set without the `Secure` attribute. The runner cares because cookies lacking `Secure` can be sent over plaintext HTTP when the browser reaches a matching origin or subdomain, exposing authentication state to network attackers or downgrade paths.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with redirect, TLS, timeout, and cookie-jar controls.
* `scanner_config`: stub-specific knobs listed below.

Optional inputs:

* `authenticated_context`: existing scoped session from the project runner, if already available.
* `known_auth_endpoints`: previously discovered login/profile URLs.
* `prior_cookie_evidence`: cookie evidence collected by other checks.
* `tls_metadata`: TLS and redirect metadata from Phase 1, if already collected.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `max_public_requests` | `4` | Maximum unauthenticated requests. |
| `max_authenticated_requests` | `4` | Maximum requests using an existing authenticated context. |
| `follow_redirects` | `true` | Capture redirect-chain cookies and the final response. |
| `require_https_for_confirmed` | `true` | Only confirm missing `Secure` when the cookie is observed from HTTPS. |
| `classify_http_only_targets` | `true` | Record candidates for sensitive cookies on HTTP targets without upgrading severity. |
| `redact_cookie_values` | `true` | Cookie values must be redacted before logs and findings. |
| `store_rejected_secure_cookies` | `false` | Optional: persist rejected evidence for cookies already using `Secure`. |

## Detection logic

Detection is deterministic and header-based.

### 1. Collect cookie evidence

Allowed unauthenticated requests:

1. `GET /`
2. `HEAD /` only if the shared runner already uses it for header collection.
3. Redirect responses while resolving `/`, up to the shared redirect limit.
4. `GET` a discovered login page when earlier phases already identified one.

Allowed authenticated requests, only when `authenticated_context` already exists:

1. `GET` the authenticated landing page supplied by the shared context.
2. `GET` the current-user/profile endpoint supplied by prior discovery.
3. `GET` one safe page that normally refreshes session cookies.

For each response, record:

* request method
* response URL and scheme
* response status code
* redirect-chain position
* whether an authenticated context was used
* every `Set-Cookie` header as a separate parsed cookie

Do not submit login forms in this spec. If no authenticated context exists, use only public and discovered read-only pages.

### 2. Parse cookie attributes

Use a standards-aware cookie parser. Extract:

* `name`
* redacted or hashed `value`
* `domain`
* `path`
* `expires`
* `max-age`
* `secure`
* `httponly`
* `samesite`
* unrecognized attributes

Attribute matching rules:

* `Secure` is case-insensitive.
* Attribute order is irrelevant.
* Presence of `Secure` is enough; it has no required value.
* Cookies set multiple times must be evaluated per response and scope.
* Malformed cookies should not crash the scan; record parser evidence and classify conservatively.

### 3. Classify cookie sensitivity

High-sensitivity cookies:

* Common session or framework names: `PHPSESSID`, `JSESSIONID`, `connect.sid`, `ASP.NET_SessionId`, `session`, `sid`, `auth`, `jwt`, `access_token`, `refresh_token`, `id_token`.
* Cookies set on authenticated pages.
* Cookies set by auth-related routes and containing long random-looking values.
* Cookies with broad `Domain` or `Path=/` scope that appear to carry login state.

Medium-sensitivity cookies:

* Names containing `session`, `sess`, `auth`, `token`, `login`, `remember`, or `sso`.
* Cookies set during login-page discovery without authenticated confirmation.

Usually non-vulnerable cookies:

* Analytics, consent, locale, theme, experiment, or preference cookies.
* CSRF helper cookies that are not authenticators.
* Load balancer affinity cookies unless project policy treats them as sensitive.

### 4. Flag missing `Secure`

Create a finding when all conditions are true:

* A `Set-Cookie` header sets a high or medium sensitivity cookie.
* The parsed attributes do not include `Secure`.
* The response is from an in-scope URL.

Scheme-aware severity:

| Observation | Status | Confidence |
| ----------- | ------ | ---------- |
| Sensitive cookie set over HTTPS without `Secure`. | `confirmed` | `high` |
| Framework session cookie set over HTTPS without `Secure`. | `confirmed` | `high` |
| `SameSite=None` cookie set without `Secure`, because modern browsers reject or downgrade the intended behavior. | `confirmed` | `high` |
| Sensitive cookie set on an HTTP-only target without `Secure`. | `candidate` | `medium` |
| Auth-looking cookie lacks `Secure`, but no authenticated context exists. | `candidate` | `medium` |
| Cookie includes `Secure`. | `rejected` | `high` |
| Previous missing-`Secure` finding no longer appears in current evidence. | `stale` | `medium` |

Do not create a vulnerability finding for:

* Cookies that already include `Secure`.
* Non-sensitive cookies.
* Out-of-scope redirect destinations.
* Cookies synthesized by the scanner, browser automation framework, or proxy.
* The mere presence of HTTP service without cookie evidence; transport policy belongs to security-header and TLS checks.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `MissingSecureSignature`, `MissingSecureFinding`.

### `MissingSecureSignature`

```ts
export interface MissingSecureSignature {
  signature_id: string;
  cookie_name_pattern: string;
  match_type: "equals" | "contains" | "regex";
  sensitivity: "low" | "medium" | "high";
  cookie_category:
    | "session"
    | "auth"
    | "access_token"
    | "refresh_token"
    | "remember_me"
    | "framework_session"
    | "csrf_helper"
    | "unknown";
  requires_https_for_confirmed: boolean;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `MissingSecureFinding`

```ts
export interface MissingSecureFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  cookie_name: string;
  cookie_value_fingerprint?: string;
  cookie_domain?: string;
  cookie_path?: string;
  source_url: string;
  source_scheme: "http" | "https";
  source_method: "GET" | "HEAD";
  source_status_code: number;
  source_context: "public" | "authenticated" | "redirect";

  observed_attributes: {
    secure: boolean;
    httponly: boolean;
    samesite?: "Strict" | "Lax" | "None" | "unknown";
    expires?: string;
    max_age?: string;
    domain?: string;
    path?: string;
  };

  cookie_category:
    | "session"
    | "auth"
    | "access_token"
    | "refresh_token"
    | "remember_me"
    | "framework_session"
    | "csrf_helper"
    | "unknown";

  sensitivity: "low" | "medium" | "high";
  title: string;
  summary: string;
  remediation: {
    summary: string;
    steps: string[];
  };

  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";
  safe: true;
  created_at: string;
  updated_at: string;
}
```

Evidence requirements:

* `source`: `cookie`
* `field`: `Set-Cookie`
* `matched_value`: cookie name, not the raw value
* `raw_excerpt`: redacted `Set-Cookie` header, for example `sid=<redacted>; Path=/; HttpOnly`
* `content_hash`: hash of the redacted header or secure raw evidence hash

Recommended remediation:

* Add `Secure` to all cookies carrying session identifiers, access tokens, refresh tokens, remember-me state, or authentication state.
* Serve authenticated areas exclusively over HTTPS.
* Keep HTTP-to-HTTPS redirects in place, but do not rely on redirects alone to protect cookies.
* Pair `Secure` with `HttpOnly` and appropriate `SameSite`, reported by their own specs.

## Safety

This check is passive and read-only unless the shared runner supplies an already-authenticated context.

Allowed:

* `GET`
* `HEAD`
* Following redirects within configured limits
* Reading `Set-Cookie` response headers
* Using an existing authenticated session to visit safe read-only pages

Not allowed:

* `POST`, `PUT`, `PATCH`, or `DELETE`
* Login attempts created by this spec
* Logout requests
* Downgrade attacks
* DNS rebinding
* Man-in-the-middle simulation
* Cookie injection or cookie tossing
* Fetching out-of-scope redirect destinations for cookie analysis
* Treating non-sensitive cookies as vulnerabilities

PII and secrets:

* Never log raw cookie values.
* Redact `Set-Cookie` values in evidence excerpts and finding summaries.
* Store cookie fingerprints only with the project-approved secret hashing helper.
* Do not send cookie evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Cookie parsing, scheme checks, and attribute checks are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It captures every `Set-Cookie` header as a separate cookie observation.
* It parses cookie attributes case-insensitively.
* It treats `Secure`, `secure`, and `SECURE` as present.
* It detects `sid=<value>; Path=/; HttpOnly; SameSite=Lax` from an HTTPS response as missing `Secure`.
* It detects `PHPSESSID=<value>; Path=/; HttpOnly` from an HTTPS response as missing `Secure`.
* It detects `SameSite=None` without `Secure` on a sensitive cookie as high-confidence.
* It rejects `sid=<value>; Path=/; Secure; HttpOnly; SameSite=Lax`.
* It records the response scheme that set the cookie.
* It marks HTTPS session/auth cookies without `Secure` as `confirmed`.
* It marks HTTP-only observations as `candidate` when `require_https_for_confirmed=true`.
* It redacts cookie values in logs and findings.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not create findings from cookies that already include `Secure`.
* It must not flag analytics, consent, locale, theme, or preference cookies by default.
* It must not hard-code hostname-to-cookie expectations.
* It must not attempt login.
* It must not call logout.
* It must not send mutating HTTP methods.
* It must not attempt protocol downgrade attacks.
* It must not perform MITM-style testing.
* It must not store raw cookie values in findings.
* It must not send cookie evidence to an LLM.
* It must not fail the whole scan when no cookies are set.

## Test fixtures

Use the synthetic fixture slug: `session-cookie-attributes`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/secure/missing-session` | HTTPS route sets `sid=vulnerable; Path=/; HttpOnly; SameSite=Lax` | `confirmed`, `high` |
| `/secure/present-session` | HTTPS route sets `sid=safe; Path=/; Secure; HttpOnly; SameSite=Lax` | `rejected`, `high` or no finding |
| `/secure/missing-framework` | HTTPS route sets `PHPSESSID=vulnerable; Path=/; HttpOnly` | `confirmed`, `high` |
| `/secure/samesite-none` | HTTPS route sets `sid=vulnerable; Path=/; HttpOnly; SameSite=None` | `confirmed`, `high` |
| `/secure/preference-cookie` | HTTPS route sets `theme=dark; Path=/` | no vulnerability finding |
| `/secure/http-only-target` | HTTP route sets `sid=vulnerable; Path=/; HttpOnly` | `candidate`, `medium` |
| `/secure/redirect-chain` | HTTPS redirect response sets a vulnerable session cookie | finding linked to redirect evidence |

Compatibility fixtures:

* `dvwa` may be used for exploratory validation if it sets `PHPSESSID` without `Secure` in the local HTTPS deployment.
* `juice-shop` may be used to verify rejection of cookies that already include `Secure`.
* Do not make acceptance depend on live fixture cookie settings that may vary by proxy, TLS termination, or container version.

## Acceptance criteria

The implementation is acceptable when:

* The check is idempotent and read-only.
* The default unauthenticated scan sends no more than `max_public_requests`.
* The authenticated scan uses only an existing authenticated context and sends no more than `max_authenticated_requests`.
* It completes within the Phase 3 request budget.
* It handles no-cookie responses without errors.
* It handles duplicate cookie names on different paths or domains.
* It handles malformed `Set-Cookie` headers without crashing.
* It handles redirects and records which response set the cookie.
* It records the scheme used when each cookie was set.
* It handles TLS failures, timeouts, and connection errors gracefully.
* It redacts cookie values consistently in logs, evidence excerpts, and findings.
* It produces deterministic statuses and confidence values.
* It stores findings with at least one evidence ID.
* It defines only `MissingSecureSignature` and `MissingSecureFinding` as stub-specific types.
* Unit tests cover cookie parsing, attribute casing, scheme-aware classification, `SameSite=None` behavior, redaction, duplicate cookie handling, redirect cookies, stale handling, and negative assertions.
* Fixture tests cover missing `Secure`, present `Secure`, framework session cookies, `SameSite=None`, preference cookies, HTTP-only targets, and redirect-chain cookies.
* AI is not called.
