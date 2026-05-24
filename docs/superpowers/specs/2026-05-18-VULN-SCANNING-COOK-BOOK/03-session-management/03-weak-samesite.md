---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 3
slug: weak-samesite
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.3 Weak `SameSite`

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

Detect sensitive cookies with missing, overly permissive, or policy-inconsistent `SameSite` attributes. The runner cares because weak `SameSite` settings increase the chance that browsers attach session cookies to cross-site requests, which can make CSRF and login/session confusion bugs easier to exploit.

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
* `cross_site_cookie_allowlist`: configured cookie names or patterns that legitimately require `SameSite=None`, such as federated login handoff cookies.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `max_public_requests` | `4` | Maximum unauthenticated requests. |
| `max_authenticated_requests` | `4` | Maximum requests using an existing authenticated context. |
| `follow_redirects` | `true` | Capture redirect-chain cookies and the final response. |
| `treat_missing_as_candidate` | `true` | Missing `SameSite` is a candidate because modern browser defaults vary by context and age. |
| `require_secure_when_none` | `true` | `SameSite=None` should be paired with `Secure`. |
| `require_strict_for_admin_cookies` | `false` | Optional stricter policy for admin-only session cookies. |
| `redact_cookie_values` | `true` | Cookie values must be redacted before logs and findings. |

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

Do not perform CSRF probes in this spec. This check observes cookie policy only.

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

Attribute rules:

* `SameSite` name matching is case-insensitive.
* Accepted values are `Strict`, `Lax`, and `None`, case-insensitive.
* Unknown values should be classified as `invalid`.
* Missing `SameSite` should be represented explicitly as `missing`.
* Duplicate cookies must be evaluated per response and path/domain scope.

### 3. Classify cookie sensitivity

High-sensitivity cookies:

* Common session or auth names: `PHPSESSID`, `JSESSIONID`, `connect.sid`, `ASP.NET_SessionId`, `session`, `sid`, `auth`, `jwt`, `access_token`, `refresh_token`, `id_token`.
* Cookies set after login or on authenticated pages.
* Cookies with broad `Domain` or `Path=/` scope that appear to carry login state.

Medium-sensitivity cookies:

* Names containing `session`, `sess`, `auth`, `token`, `login`, `remember`, or `sso`.
* Cookies set by discovered login pages without authenticated confirmation.

Usually non-vulnerable cookies:

* Analytics, consent, locale, theme, experiment, or preference cookies.
* CSRF helper cookies that are not authenticators.
* Short-lived OAuth/SSO correlation cookies that are configured in `cross_site_cookie_allowlist`.

### 4. Classify `SameSite` weakness

Create a finding only for high or medium sensitivity cookies.

| Observation | Status | Confidence |
| ----------- | ------ | ---------- |
| Sensitive cookie explicitly uses `SameSite=None` and is not allowlisted for cross-site use. | `candidate` | `high` |
| Sensitive cookie explicitly uses `SameSite=None` without `Secure`. | `confirmed` | `high` |
| Sensitive cookie has no `SameSite` attribute and `treat_missing_as_candidate=true`. | `candidate` | `medium` |
| Sensitive cookie has an invalid `SameSite` value. | `confirmed` | `medium` |
| Admin-sensitive cookie uses `Lax` while `require_strict_for_admin_cookies=true`. | `candidate` | `medium` |
| Sensitive cookie uses `Strict`, or uses `Lax` under the default policy. | `rejected` | `high` |
| Previous weak-`SameSite` finding no longer appears in current evidence. | `stale` | `medium` |

Do not claim CSRF exploitability from this spec alone. CSRF exploitability requires Phase 7 tests for state-changing requests, token behavior, request method, content type, and user interaction.

Do not create a vulnerability finding for:

* Non-sensitive cookies.
* Cookies in `cross_site_cookie_allowlist`.
* `SameSite=Lax` under the default policy.
* `SameSite=Strict`.
* Cookies observed only from out-of-scope redirect destinations.
* Cookies synthesized by the scanner, browser automation framework, or proxy.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `WeakSameSiteSignature`, `WeakSameSiteFinding`.

### `WeakSameSiteSignature`

```ts
export interface WeakSameSiteSignature {
  signature_id: string;
  cookie_name_pattern: string;
  match_type: "equals" | "contains" | "regex";
  cookie_category:
    | "session"
    | "auth"
    | "access_token"
    | "refresh_token"
    | "remember_me"
    | "framework_session"
    | "csrf_helper"
    | "oauth_state"
    | "unknown";
  sensitivity: "low" | "medium" | "high";
  expected_samesite: "Strict" | "Lax" | "not_none";
  allow_missing: boolean;
  allow_none_when_configured: boolean;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `WeakSameSiteFinding`

```ts
export interface WeakSameSiteFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  cookie_name: string;
  cookie_value_fingerprint?: string;
  cookie_domain?: string;
  cookie_path?: string;
  source_url: string;
  source_method: "GET" | "HEAD";
  source_status_code: number;
  source_context: "public" | "authenticated" | "redirect";

  observed_attributes: {
    secure: boolean;
    httponly: boolean;
    samesite: "Strict" | "Lax" | "None" | "missing" | "invalid";
    raw_samesite_value?: string;
    expires?: string;
    max_age?: string;
    domain?: string;
    path?: string;
  };

  weakness_kind:
    | "missing_samesite"
    | "explicit_none"
    | "none_without_secure"
    | "invalid_samesite"
    | "lax_where_strict_required";

  cookie_category:
    | "session"
    | "auth"
    | "access_token"
    | "refresh_token"
    | "remember_me"
    | "framework_session"
    | "csrf_helper"
    | "oauth_state"
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
* `raw_excerpt`: redacted `Set-Cookie` header, for example `sid=<redacted>; Path=/; Secure; HttpOnly; SameSite=None`
* `content_hash`: hash of the redacted header or secure raw evidence hash

Recommended remediation:

* Set `SameSite=Lax` or `SameSite=Strict` on session and auth cookies unless cross-site use is explicitly required.
* Use `SameSite=Strict` for high-risk admin or account-management cookies when product flows allow it.
* If `SameSite=None` is required, pair it with `Secure`, keep the cookie short-lived, and document the cross-site use case.
* Do not rely on `SameSite` as the only CSRF defense for state-changing actions.

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
* CSRF proof-of-concept submissions
* Cross-site browser automation
* Hidden form submissions
* Cookie injection or cookie tossing
* Treating `SameSite=Lax` as a vulnerability under the default policy

PII and secrets:

* Never log raw cookie values.
* Redact `Set-Cookie` values in evidence excerpts and finding summaries.
* Store cookie fingerprints only with the project-approved secret hashing helper.
* Do not send cookie evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Cookie parsing, allowlist matching, and attribute classification are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It captures every `Set-Cookie` header as a separate cookie observation.
* It parses `SameSite` case-insensitively.
* It normalizes `SameSite=strict`, `SameSite=Lax`, and `SameSite=NONE`.
* It detects a sensitive cookie with no `SameSite` as `candidate`, `medium` when `treat_missing_as_candidate=true`.
* It detects a sensitive cookie with `SameSite=None` and no allowlist entry as `candidate`, `high`.
* It detects `SameSite=None` without `Secure` as `confirmed`, `high`.
* It detects invalid values such as `SameSite=Loose` as `confirmed`, `medium`.
* It rejects `SameSite=Strict`.
* It rejects `SameSite=Lax` under the default policy.
* It respects `cross_site_cookie_allowlist`.
* It redacts cookie values in logs and findings.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not claim CSRF exploitability from cookie attributes alone.
* It must not flag non-sensitive analytics, consent, locale, theme, or preference cookies by default.
* It must not flag allowlisted SSO/OAuth correlation cookies that legitimately require `SameSite=None`.
* It must not hard-code hostname-to-cookie expectations.
* It must not attempt login.
* It must not call logout.
* It must not send mutating HTTP methods.
* It must not submit CSRF payloads or forms.
* It must not run cross-site browser automation.
* It must not store raw cookie values in findings.
* It must not send cookie evidence to an LLM.
* It must not fail the whole scan when no cookies are set.

## Test fixtures

Use the synthetic fixture slug: `session-cookie-attributes`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/samesite/missing-session` | Sets `sid=vulnerable; Path=/; Secure; HttpOnly` | `candidate`, `medium` |
| `/samesite/none-session` | Sets `sid=vulnerable; Path=/; Secure; HttpOnly; SameSite=None` | `candidate`, `high` |
| `/samesite/none-without-secure` | Sets `sid=vulnerable; Path=/; HttpOnly; SameSite=None` | `confirmed`, `high` |
| `/samesite/invalid` | Sets `sid=vulnerable; Path=/; Secure; HttpOnly; SameSite=Loose` | `confirmed`, `medium` |
| `/samesite/lax-session` | Sets `sid=safe; Path=/; Secure; HttpOnly; SameSite=Lax` | `rejected`, `high` or no finding |
| `/samesite/strict-session` | Sets `sid=safe; Path=/; Secure; HttpOnly; SameSite=Strict` | `rejected`, `high` or no finding |
| `/samesite/allowlisted-sso` | Sets allowlisted `sso_state=value; Path=/; Secure; HttpOnly; SameSite=None` | no vulnerability finding |
| `/samesite/preference-cookie` | Sets `theme=dark; Path=/` | no vulnerability finding |

Compatibility fixtures:

* `juice-shop` and `dvwa` may be used for exploratory validation of real cookie settings.
* Do not make acceptance depend on live fixture cookie settings that may vary by reverse proxy, browser defaults, or container version.

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
* It handles unknown or invalid `SameSite` values deterministically.
* It redacts cookie values consistently in logs, evidence excerpts, and findings.
* It produces deterministic statuses and confidence values.
* It stores findings with at least one evidence ID.
* It defines only `WeakSameSiteSignature` and `WeakSameSiteFinding` as stub-specific types.
* Unit tests cover cookie parsing, `SameSite` normalization, missing value classification, `None` classification, allowlist behavior, invalid values, redaction, duplicate cookie handling, stale handling, and negative assertions.
* Fixture tests cover missing `SameSite`, `SameSite=None`, `None` without `Secure`, invalid value, `Lax`, `Strict`, allowlisted SSO cookies, and preference cookies.
* AI is not called.
