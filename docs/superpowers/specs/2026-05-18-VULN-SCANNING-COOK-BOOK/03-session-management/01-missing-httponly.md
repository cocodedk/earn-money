---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 1
slug: missing-httponly
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.1 Missing `HttpOnly`

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

Detect session-bearing cookies that are set without the `HttpOnly` attribute. The runner cares because cookies readable by JavaScript can be stolen through XSS, malicious browser extensions, injected third-party scripts, or DOM gadget abuse, turning a client-side issue into session theft.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with redirect, TLS, timeout, and cookie-jar controls.
* `scanner_config`: stub-specific knobs listed below.

Optional inputs:

* `authenticated_context`: existing scoped session from the project runner, if already available.
* `known_auth_endpoints`: previously discovered login/logout/profile URLs.
* `prior_cookie_evidence`: `Evidence` rows collected by Phase 1 or other session-management checks.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `max_public_requests` | `4` | Maximum unauthenticated requests. |
| `max_authenticated_requests` | `4` | Maximum requests using an existing authenticated context. |
| `follow_redirects` | `true` | Capture redirect-chain cookies and the final response. |
| `include_static_asset_cookies` | `false` | Do not fetch extra assets only for cookies unless enabled. |
| `sensitive_cookie_name_regex` | see below | Identifies cookies likely to carry sessions or auth state. |
| `redact_cookie_values` | `true` | Cookie values must be redacted before logs and findings. |
| `store_rejected_safe_cookies` | `false` | Optional: persist rejected evidence for non-sensitive cookies. |

Default sensitive cookie name regex, case-insensitive:

```text
(^|[_\-.])(sid|session|sess|auth|token|jwt|access|refresh|id_token|remember|login|sso|csrf_session)([_\-.]|$)|^(PHPSESSID|JSESSIONID|ASP\.?NET_SessionId|connect\.sid|sid)$
```

The regex is a classifier, not proof of exploitability. The runner must combine cookie name, attributes, response context, and authenticated state before setting confidence.

## Detection logic

Detection is deterministic and header-based.

### 1. Collect `Set-Cookie` evidence

Allowed unauthenticated requests:

1. `GET /`
2. `HEAD /` only if the shared runner already uses it for header collection.
3. Redirect responses while resolving `/`, up to the shared redirect limit.
4. `GET /login`, `/signin`, or discovered auth page only when already discovered by earlier phases or bounded login-route discovery.

Allowed authenticated requests, only when `authenticated_context` already exists:

1. `GET` the account landing page supplied by the authenticated context.
2. `GET` the current-user/profile endpoint supplied by prior discovery.
3. `GET` one safe application page that normally refreshes session cookies.
4. `GET` logout page is not allowed in this spec; logout behavior belongs to specs 3.7 and 3.12.

For every response:

* Preserve each `Set-Cookie` header as a separate parsed cookie.
* Capture cookies from redirect responses and the final response.
* Record response URL, status code, request method, redirect position, and whether an authenticated context was used.
* Redact cookie values before logs and finding summaries.
* Store raw cookie values only if the project has secure evidence storage; otherwise store hashed or redacted values.

### 2. Parse cookie attributes

Use a standards-aware cookie parser. Do not split only on semicolons if the project has a safer parser available.

For each `Set-Cookie`, extract:

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

* `HttpOnly` is case-insensitive.
* Attribute order is irrelevant.
* Attribute value is irrelevant; presence of the attribute is enough.
* Duplicate `Set-Cookie` headers with the same cookie name must be evaluated separately by response and path/domain scope.
* Malformed cookies should produce parser evidence and a `candidate` finding only when the cookie is still clearly session-like.

### 3. Classify cookie sensitivity

Classify a cookie before checking whether missing `HttpOnly` is a finding.

High-sensitivity cookies:

* Name directly matches common session/auth cookies such as `PHPSESSID`, `JSESSIONID`, `connect.sid`, `ASP.NET_SessionId`, `session`, `sid`, `auth`, `access_token`, `refresh_token`, `id_token`, or `jwt`.
* Cookie is set after login or on an authenticated page.
* Cookie has a long random-looking value and is used with authenticated context evidence.
* Cookie path or domain applies broadly to application routes.

Medium-sensitivity cookies:

* Name contains `session`, `sess`, `auth`, `token`, `login`, `remember`, or `sso`.
* Cookie is set by an auth-related route, but no authenticated control is available.
* Cookie is a framework session cookie inferred from a known name.

Low-sensitivity or usually non-vulnerable cookies:

* Analytics, A/B testing, consent, locale, theme, feature flag, tracking, or preference cookies.
* CSRF token cookies intentionally readable by JavaScript under a double-submit-cookie pattern.
* Static asset cache cookies.
* Load balancer affinity cookies such as `AWSALB`, `AWSALBCORS`, `ARRAffinity`, or `BIGipServer`, unless project policy treats them as sensitive.

### 4. Flag missing `HttpOnly`

Create a finding when all conditions are true:

* A `Set-Cookie` header sets a cookie.
* The cookie is classified as high or medium sensitivity.
* The parsed attributes do not include `HttpOnly`.
* The evidence is from an in-scope target URL.

Do not create a vulnerability finding for:

* Non-sensitive preference, analytics, locale, or consent cookies.
* CSRF cookies that are intentionally script-readable and not session authenticators.
* Cookies that already include `HttpOnly`.
* Cookies observed only from out-of-scope redirect destinations.
* Cookies synthesized by the scanner, browser automation framework, or local proxy.

### 5. Status and confidence

Use these rules:

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Known session/auth cookie from authenticated or auth-related response lacks `HttpOnly`. | `confirmed` | `high` |
| Framework session cookie such as `PHPSESSID`, `JSESSIONID`, `connect.sid`, or `ASP.NET_SessionId` lacks `HttpOnly`. | `confirmed` | `high` |
| Cookie name strongly suggests auth/session but no authenticated context exists. | `candidate` | `medium` |
| Cookie appears sensitive but parser could not fully parse attributes. | `candidate` | `low` |
| Cookie is present with `HttpOnly`. | `rejected` | `high` |
| Previous missing-`HttpOnly` finding no longer appears in the current scan. | `stale` | `medium` |

If the implementation does not persist negative results, it may omit `rejected` findings, but unit tests must still cover rejected classification.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `MissingHttpOnlySignature`, `MissingHttpOnlyFinding`.

### `MissingHttpOnlySignature`

```ts
export interface MissingHttpOnlySignature {
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
    | "csrf_session"
    | "unknown";
  requires_authenticated_context: boolean;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `MissingHttpOnlyFinding`

```ts
export interface MissingHttpOnlyFinding {
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
    | "csrf_session"
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
* `raw_excerpt`: redacted `Set-Cookie` header, for example `PHPSESSID=<redacted>; Path=/`
* `content_hash`: hash of the redacted header or secure raw evidence hash, depending on project policy

Recommended remediation:

* Set `HttpOnly` on all cookies that carry session identifiers, access tokens, refresh tokens, remember-me tokens, or authentication state.
* Keep CSRF token cookies script-readable only when the application intentionally uses a double-submit pattern and the cookie is not itself an authenticator.
* Pair `HttpOnly` with `Secure` and an appropriate `SameSite` value, but report missing `Secure` and weak `SameSite` in their own specs.

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
* XSS payloads or JavaScript execution to prove cookie theft
* Browser extension simulation
* Cookie tossing or cookie injection
* Fetching out-of-scope redirect destinations for cookie analysis
* Treating non-sensitive cookies as vulnerabilities

PII and secrets:

* Never log raw cookie values.
* Never store authorization headers, CSRF tokens, or cookie values in finding summaries.
* Redact `Set-Cookie` values in normal logs.
* Hash cookie values only with the project-approved secret hashing helper when correlation is required.
* Do not send cookie evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Cookie parsing, sensitivity classification, and attribute checks are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It captures every `Set-Cookie` header as a separate cookie observation.
* It parses cookie attributes case-insensitively.
* It treats `HttpOnly`, `httponly`, and `HTTPONLY` as present.
* It detects `PHPSESSID=<value>; Path=/` as missing `HttpOnly`.
* It detects `connect.sid=<value>; Path=/; Secure; SameSite=Lax` as missing `HttpOnly`.
* It rejects `session=<value>; Path=/; HttpOnly; Secure; SameSite=Lax`.
* It redacts cookie values in logs and finding summaries.
* It links each finding to at least one `Evidence` record.
* It marks direct session/auth cookies without `HttpOnly` as `confirmed`.
* It marks auth-looking cookies without authenticated context as `candidate`.
* It can mark previous findings `stale` when the current scan no longer observes the cookie.
* It keeps missing `Secure` and weak `SameSite` out of this finding type.

Negative assertions:

* It must not create findings from cookies that already include `HttpOnly`.
* It must not flag analytics, consent, locale, theme, or preference cookies by default.
* It must not flag an intentionally script-readable CSRF token cookie as a session cookie unless evidence shows it authenticates the session.
* It must not hard-code hostname-to-cookie expectations.
* It must not attempt login.
* It must not call logout.
* It must not send mutating HTTP methods.
* It must not inject XSS payloads.
* It must not read cookies through JavaScript as proof.
* It must not store raw cookie values in findings.
* It must not send cookie evidence to an LLM.
* It must not fail the whole scan when no cookies are set.

## Test fixtures

Use a new synthetic fixture slug: `session-cookie-attributes`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/httponly/missing-session` | Sets `sid=vulnerable; Path=/; Secure; SameSite=Lax` | `confirmed`, `high` |
| `/httponly/present-session` | Sets `sid=safe; Path=/; HttpOnly; Secure; SameSite=Lax` | `rejected`, `high` or no finding |
| `/httponly/missing-framework` | Sets `PHPSESSID=vulnerable; Path=/` | `confirmed`, `high` |
| `/httponly/preference-cookie` | Sets `theme=dark; Path=/` | no vulnerability finding |
| `/httponly/csrf-readable` | Sets `csrf_token=value; Path=/; SameSite=Lax` and marks it as non-auth CSRF fixture cookie | no vulnerability finding |
| `/httponly/mixed-cookies` | Sets one safe session cookie, one vulnerable session cookie, and one preference cookie | one finding for the vulnerable session cookie |
| `/httponly/redirect-chain` | Sets a vulnerable session cookie on a redirect response | finding linked to redirect evidence |

Compatibility fixtures:

* `dvwa` may be used for exploratory validation if it sets `PHPSESSID` without `HttpOnly` in the local deployment.
* `juice-shop` may be used to verify that modern cookies with `HttpOnly` are rejected.
* Do not make acceptance depend on live fixture cookie settings that may vary by reverse proxy or container version; use synthetic responses for deterministic tests.

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
* It handles TLS failures, timeouts, and connection errors gracefully.
* It redacts cookie values consistently in logs, evidence excerpts, and findings.
* It produces deterministic statuses and confidence values.
* It stores findings with at least one evidence ID.
* It defines only `MissingHttpOnlySignature` and `MissingHttpOnlyFinding` as stub-specific types.
* Unit tests cover cookie parsing, attribute casing, sensitivity classification, redaction, duplicate cookie handling, redirect cookies, stale handling, and negative assertions.
* Fixture tests cover missing `HttpOnly`, present `HttpOnly`, framework session cookies, preference cookies, CSRF-readable cookies, mixed cookies, and redirect-chain cookies.
* AI is not called.
