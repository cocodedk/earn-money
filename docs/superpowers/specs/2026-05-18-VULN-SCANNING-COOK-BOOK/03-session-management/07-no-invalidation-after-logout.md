---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 7
slug: no-invalidation-after-logout
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.7 No invalidation after logout

> Phase 3 — Session management · Category: Session lifecycle

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

Detect logout flows that leave the browser session cookie valid after logout. The runner cares because users expect logout to revoke the active web session; if the old cookie still works, stolen or cached sessions can remain usable after logout.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar support.
* `scanner_config`: stub-specific knobs listed below.

Required for confirmed testing:

* `test_account`: scoped credentials from fixture config, scan config, or approved credential store.
* `login_flow`: discovered login form/API metadata, or a fixture adapter that knows how to authenticate safely.
* `logout_flow`: known logout URL/form/API from fixture config, scan config, or prior discovery.
* `safe_authenticated_check`: endpoint or page that proves authenticated state without exposing sensitive data, such as `/me` returning only a fixture username.

Optional inputs:

* `csrf_extractor`: shared helper for login or logout forms with CSRF tokens.
* `known_session_cookie_names`: session cookie names from prior cookie checks.
* `post_logout_expected_markers`: configured markers such as login redirect, `401`, or generic logged-out text.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled with scoped credentials. |
| `allow_logout_submission` | `false` | Must be explicitly enabled with a known logout flow. |
| `max_login_attempts` | `1` | Prevents account lockout and noisy auth logs. |
| `max_logout_attempts` | `1` | Prevents repeated state changes. |
| `max_reuse_checks` | `2` | Bounded post-logout checks with the old cookie jar. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `follow_redirects` | `false` | Keep logout and reuse redirects visible as evidence. |
| `redact_cookie_values` | `true` | Cookie values must be redacted before logs and findings. |

## Detection logic

Detection is deterministic and compares access to a safe authenticated marker before and after logout.

### 1. Authenticate with an isolated client

Only run when `allow_login_submission=true` and scoped credentials are available.

1. Create a fresh isolated HTTP client and cookie jar.
2. Fetch the login form or fixture login endpoint.
3. Refresh CSRF or hidden fields when needed.
4. Submit exactly one valid login request.
5. Confirm authentication using `safe_authenticated_check`.
6. Capture the primary session cookie fingerprint and authenticated marker evidence.

Do not continue if authentication cannot be proven safely.

### 2. Perform one known logout

Only run when `allow_logout_submission=true` and `logout_flow` is known.

1. Submit the logout request using the same isolated client.
2. Capture logout response status, redirects, and `Set-Cookie` headers.
3. Record whether the server expires or overwrites session cookies.
4. Do not infer success from UI text alone; require an expected redirect, status, cookie expiry, or configured logged-out marker.

Allowed logout methods are the methods actually used by the known logout flow. Do not guess logout endpoints or methods.

### 3. Reuse old session state

After logout, attempt to access only `safe_authenticated_check` using the same cookie jar that held the pre-logout session.

Expected safe results:

* `401` or `403`.
* Redirect to login.
* Generic logged-out response.
* Authenticated marker is absent.
* Session cookie is expired or replaced.

Vulnerable results:

* The same authenticated marker is still returned.
* The endpoint still returns a fixture username or account identifier after logout.
* The old session cookie remains accepted without reauthentication.

Do not fetch arbitrary private resources. Do not enumerate account data. Do not use the old cookie in another browser or machine unless a fixture explicitly requires that variant.

### 4. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Safe authenticated marker is accessible with the old cookie after logout. | `confirmed` | `high` |
| Logout response does not expire any session cookie and post-logout check is inconclusive. | `candidate` | `medium` |
| Post-logout check redirects to login, returns `401/403`, or removes authenticated marker. | `rejected` | `high` |
| Test aborted because credentials, logout flow, CSRF, CAPTCHA, rate limit, or safety preconditions are missing. | `stale` | `low` |

This spec covers browser cookie/session invalidation. Bearer tokens, JWTs, refresh tokens, and API tokens accepted after logout belong to spec 3.12.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `NoInvalidationAfterLogoutSignature`, `NoInvalidationAfterLogoutFinding`.

### `NoInvalidationAfterLogoutSignature`

```ts
export interface NoInvalidationAfterLogoutSignature {
  signature_id: string;
  login_url: string;
  logout_url: string;
  safe_check_url: string;
  session_cookie_name: string;
  logout_method: "GET" | "POST";
  requires_valid_credentials: true;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `NoInvalidationAfterLogoutFinding`

```ts
export interface NoInvalidationAfterLogoutFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  login_url: string;
  logout_url: string;
  safe_check_url: string;
  logout_method: "GET" | "POST";
  authenticated_before_logout: boolean;
  authenticated_after_logout: boolean;

  session_cookie_name: string;
  session_cookie_domain?: string;
  session_cookie_path?: string;
  pre_logout_cookie_fingerprint?: string;
  post_logout_cookie_fingerprint?: string;

  logout_observation: {
    status_code: number;
    redirect_target_redacted?: string;
    cookie_expired: boolean;
    cookie_replaced: boolean;
    logged_out_marker_seen: boolean;
  };

  reuse_observation: {
    status_code: number;
    redirect_target_redacted?: string;
    authenticated_marker_seen: boolean;
    expected_logged_out_marker_seen: boolean;
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
* Pre-logout authenticated marker evidence.
* Logout request and response evidence.
* Session cookie expiry/replacement evidence with redacted values.
* Post-logout reuse check evidence against the safe authenticated marker.

Recommended remediation:

* Invalidate the server-side session record during logout.
* Expire the browser session cookie with `Max-Age=0` or an expired `Expires` value.
* Reject the old session identifier on subsequent requests.
* Invalidate related server-side WebSocket/session state where applicable.
* Keep bearer token revocation aligned with spec 3.12.

## Safety

This check is active because it logs in and logs out of a scoped test account.

Allowed:

* `GET` login page and safe authenticated marker.
* One valid login request when `allow_login_submission=true`.
* One known logout request when `allow_logout_submission=true`.
* At most `max_reuse_checks` requests to the configured safe authenticated marker.

Not allowed:

* Password guessing.
* Username guessing.
* Discovering or brute forcing logout endpoints.
* More than the configured login/logout budgets.
* Testing real user accounts not explicitly scoped.
* Bypassing MFA, CAPTCHA, WAF, lockout, or rate limits.
* Continuing after `429`, lockout wording, abuse detection, or CAPTCHA.
* Fetching arbitrary private pages after logout.
* Reusing captured cookies outside the isolated test client.
* Testing bearer/JWT token reuse in this spec.

PII and secrets:

* Never log passwords, CSRF tokens, authorization headers, or raw cookie values.
* Redact usernames/emails unless fixture-only synthetic identifiers are used.
* Store cookie fingerprints only with the project-approved secret hashing helper.
* Keep safe authenticated marker evidence minimal and fixture-friendly.
* Do not send auth or cookie evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Login/logout state comparison and cookie reuse checks are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It uses an isolated cookie jar.
* It submits at most one valid login when explicitly enabled and scoped credentials exist.
* It proves authentication before logout using `safe_authenticated_check`.
* It submits only a known logout flow.
* It records whether logout expires or replaces the session cookie.
* It performs a bounded post-logout check only against `safe_authenticated_check`.
* It creates a `confirmed`, `high` finding when the authenticated marker is still accessible after logout.
* It creates a `rejected`, `high` result or no vulnerability finding when post-logout access is denied.
* It marks the test `stale`, `low` when credentials, logout flow, CSRF, CAPTCHA, rate limits, or safety preconditions are missing.
* It redacts credentials, CSRF tokens, authorization headers, and cookie values.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit guessed usernames or passwords.
* It must not brute force logout paths.
* It must not perform more than the configured request budget.
* It must not use real accounts unless explicitly scoped.
* It must not bypass MFA, CAPTCHA, WAF, rate limits, or lockout.
* It must not fetch arbitrary private resources after logout.
* It must not reuse captured cookies outside the isolated test client.
* It must not test bearer/JWT token reuse here.
* It must not store raw passwords, CSRF tokens, authorization headers, or cookie values.
* It must not send auth evidence to an LLM.
* It must not mark a finding confirmed without proof of both successful login and successful logout attempt.

## Test fixtures

Use the synthetic fixture slug: `session-lifecycle`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/logout/vulnerable/login` + `/logout/vulnerable/logout` + `/logout/vulnerable/me` | Login succeeds, logout returns success, old `sid` still accesses `/me`. | `confirmed`, `high` |
| `/logout/safe/login` + `/logout/safe/logout` + `/logout/safe/me` | Logout expires server-side session and `/me` redirects or returns `401`. | `rejected`, `high` or no finding |
| `/logout/cookie-only/login` + `/logout/cookie-only/logout` + `/logout/cookie-only/me` | Logout clears cookie but server session remains unreachable without cookie. | no vulnerability finding |
| `/logout/no-cookie-expiry/login` + `/logout/no-cookie-expiry/logout` + `/logout/no-cookie-expiry/me` | Logout response does not expire cookie but server rejects old session. | `rejected`, `high`; optional hardening note outside this spec |
| `/logout/csrf/login` + `/logout/csrf/logout` + `/logout/csrf/me` | Logout requires CSRF token. | Runner refreshes token and detects correctly. |
| `/logout/captcha/login` | Shows CAPTCHA or abuse marker before login. | `stale`, `low`; runner stops. |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Safe marker: `/me` returns only synthetic account ID and auth state
* Account and session store reset between tests

Compatibility fixtures:

* `dvwa` may be used for exploratory adapter work if deterministic login/logout and resettable state are available.
* `juice-shop` and `webgoat` may be used only as secondary compatibility checks, not primary acceptance fixtures.

## Acceptance criteria

The implementation is acceptable when:

* The check is deterministic against the fixture.
* It uses isolated clients and cookie jars.
* It performs no login unless `allow_login_submission=true`.
* It performs no logout unless `allow_logout_submission=true`.
* It completes within the configured request, login, logout, and reuse-check budgets.
* It handles missing login forms, missing logout flows, missing credentials, invalid CSRF, redirects, TLS failures, timeouts, and connection errors gracefully.
* It stops on CAPTCHA, MFA challenge without configured fixture secret, lockout, WAF block, abuse detection, or `429`.
* It redacts credentials, CSRF tokens, authorization headers, and cookie values.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `candidate`, `rejected`, and `stale` statuses correctly.
* It defines only `NoInvalidationAfterLogoutSignature` and `NoInvalidationAfterLogoutFinding` as stub-specific types.
* Unit tests cover login/logout flow handling, CSRF refresh, authenticated-marker detection, cookie expiry detection, post-logout reuse checks, redaction, safety aborts, and negative assertions.
* Fixture tests cover vulnerable logout, safe logout, cookie-only clearing, missing cookie expiry with server invalidation, CSRF logout, and CAPTCHA abort.
* AI is not called.
