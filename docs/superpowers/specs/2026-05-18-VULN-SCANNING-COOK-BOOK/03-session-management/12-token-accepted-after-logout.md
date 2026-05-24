---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 12
slug: token-accepted-after-logout
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.12 Token accepted after logout

> Phase 3 — Session management · Category: Token handling

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

Detect access, ID, session, or refresh tokens that remain accepted after logout. The runner cares because logout should revoke or invalidate token-backed sessions, especially for APIs and SPAs where browser cookie invalidation alone does not stop bearer-token reuse.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar and header controls.
* `scanner_config`: stub-specific knobs listed below.

Required for confirmed testing:

* `test_account`: scoped credentials from fixture config, scan config, or approved credential store.
* `login_flow`: known safe login flow that returns or stores a token.
* `logout_flow`: known logout URL/form/API.
* `safe_token_check`: endpoint that proves token-authenticated state without exposing sensitive data.

Optional inputs:

* `refresh_flow`: known token-refresh endpoint, used only when refresh-token reuse testing is explicitly enabled.
* `csrf_extractor`: shared helper for login/logout forms with CSRF tokens.
* `prior_token_evidence`: token evidence collected by earlier checks.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled with scoped credentials. |
| `allow_logout_submission` | `false` | Must be explicitly enabled with a known logout flow. |
| `allow_access_token_reuse_check` | `false` | Must be explicitly enabled for old access-token reuse. |
| `allow_refresh_token_reuse_check` | `false` | Disabled by default because refresh may issue new credentials. |
| `max_login_attempts` | `1` | Prevents account lockout and noisy auth logs. |
| `max_logout_attempts` | `1` | Prevents repeated state changes. |
| `max_token_reuse_requests` | `2` | Bounded token reuse checks. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `follow_redirects` | `false` | Keep token-check redirects visible as evidence. |
| `redact_token_values` | `true` | Token values must be redacted before logs and findings. |

## Detection logic

Detection is deterministic and compares token acceptance before and after logout.

### 1. Authenticate and capture scoped token

Only run when `allow_login_submission=true` and scoped credentials are available.

1. Create a fresh isolated HTTP client.
2. Perform one known safe login.
3. Capture token-bearing evidence:

   * `Authorization` bearer token from auth response.
   * Token-bearing response fields such as `access_token`, `id_token`, `refresh_token`.
   * JWT or opaque token stored in cookies, when the app uses token cookies.
4. Confirm the token works against `safe_token_check`.
5. Store only token fingerprints and redacted excerpts.

Do not continue if token-authenticated state cannot be proven safely.

### 2. Perform one known logout

Only run when `allow_logout_submission=true` and `logout_flow` is known.

1. Submit logout using the authenticated client.
2. Capture logout response status, redirects, and token/cookie clearing behavior.
3. Confirm logout through configured marker, redirect, status, or fixture oracle.

Do not infer logout success from UI text alone.

### 3. Reuse old access/session token

Only run when `allow_access_token_reuse_check=true`.

1. Create a new isolated client with no cookies unless the token was cookie-bound and the fixture explicitly requires cookie-token behavior.
2. Send the old token to `safe_token_check` using the same carrier where it was originally observed, such as `Authorization: Bearer`.
3. Compare post-logout response to the pre-logout token baseline.

Vulnerable signals:

* Safe marker still returns authenticated state for the old token.
* API still returns fixture account identity after logout.
* Token is accepted with the same scopes after logout.

Safe signals:

* `401` or `403`.
* Redirect to login.
* Token-specific error such as `invalid_token`, `expired_token`, or `revoked_token`.
* Authenticated marker is absent.

### 4. Optional refresh-token reuse

Only run when `allow_refresh_token_reuse_check=true`, `refresh_flow` is known, and the program explicitly allows token refresh testing.

1. Submit the old refresh token to the known refresh endpoint.
2. Do not use any newly issued token beyond confirming whether one was issued.
3. Record whether refresh succeeded after logout.

Refresh-token reuse after logout is a separate high-value signal because it can create new sessions after the user logs out.

### 5. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Old access/session token remains accepted by safe marker after logout. | `confirmed` | `high` |
| Old refresh token issues a new token after logout. | `confirmed` | `high` |
| Logout response does not clear token client-side and post-logout token check is inconclusive. | `candidate` | `medium` |
| Old token is rejected after logout. | `rejected` | `high` |
| Test aborted because credentials, token, logout flow, safe marker, rate limit, or safety precondition is missing. | `stale` | `low` |

Browser cookie-only session invalidation belongs to spec 3.7. This spec focuses on explicit bearer/JWT/API tokens.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `TokenAcceptedAfterLogoutSignature`, `TokenAcceptedAfterLogoutFinding`.

### `TokenAcceptedAfterLogoutSignature`

```ts
export interface TokenAcceptedAfterLogoutSignature {
  signature_id: string;
  token_kind:
    | "access_token"
    | "id_token"
    | "session_jwt"
    | "refresh_token"
    | "opaque_bearer";
  token_carrier: "authorization_header" | "cookie" | "json_body";
  logout_url: string;
  safe_check_url: string;
  requires_valid_credentials: true;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `TokenAcceptedAfterLogoutFinding`

```ts
export interface TokenAcceptedAfterLogoutFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  token_kind:
    | "access_token"
    | "id_token"
    | "session_jwt"
    | "refresh_token"
    | "opaque_bearer";
  token_carrier: "authorization_header" | "cookie" | "json_body";
  token_name?: string;
  token_fingerprint: string;

  login_url: string;
  logout_url: string;
  safe_check_url: string;
  refresh_url?: string;

  pre_logout_check: {
    status_code: number;
    authenticated_marker_seen: boolean;
  };

  logout_observation: {
    status_code: number;
    redirect_target_redacted?: string;
    logout_success_marker_seen: boolean;
    token_cleared_client_side: boolean;
  };

  post_logout_token_check: {
    status_code: number;
    authenticated_marker_seen: boolean;
    token_error_code?: string;
    refresh_issued_new_token: boolean;
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
* Token capture evidence with redacted token values.
* Pre-logout safe token check evidence.
* Logout request and response evidence.
* Post-logout old-token check evidence.
* Optional refresh-token reuse evidence when enabled.

Recommended remediation:

* Revoke access/session tokens on logout or keep them short-lived enough that logout semantics are explicit.
* Revoke refresh tokens on logout.
* Maintain server-side token revocation state for JWTs where logout must invalidate active sessions.
* Rotate refresh tokens and invalidate token families after logout, password change, MFA reset, and account recovery.
* Clear client-side token storage during logout, but do not rely on client clearing alone.

## Safety

This check is active because it logs in, logs out, and reuses a scoped old token against a safe marker.

Allowed:

* One valid login request when `allow_login_submission=true`.
* One known logout request when `allow_logout_submission=true`.
* At most `max_token_reuse_requests` old-token checks against `safe_token_check`.
* Optional refresh-token reuse only when explicitly enabled.

Not allowed:

* Password guessing.
* Username guessing.
* Discovering or brute forcing logout or refresh endpoints.
* Reusing tokens against arbitrary API endpoints.
* Using newly issued refresh output beyond confirming issuance.
* Changing token claims.
* Token replay outside the isolated test client and safe marker.
* Testing real user tokens not explicitly scoped.
* Continuing after WAF, abuse detection, lockout, or `429`.

PII and secrets:

* Never log passwords, CSRF tokens, authorization headers, or raw token values.
* Redact usernames/emails unless fixture-only synthetic identifiers are used.
* Store token fingerprints only with the project-approved secret hashing helper.
* Keep safe marker evidence minimal and fixture-friendly.
* Do not send token evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Token reuse and response comparison are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It uses isolated clients for login/logout and old-token reuse.
* It captures and fingerprints token values without logging raw tokens.
* It proves the token works before logout using `safe_token_check`.
* It submits only a known logout flow.
* It confirms logout before classifying post-logout token reuse.
* It sends the old token only to `safe_token_check`.
* It creates a `confirmed`, `high` finding when the old token still authenticates after logout.
* It creates a `confirmed`, `high` finding when an old refresh token issues a new token after logout.
* It creates a `rejected`, `high` result or no vulnerability finding when the old token is rejected after logout.
* It marks the test `stale`, `low` when required preconditions are missing.
* It redacts credentials, CSRF tokens, authorization headers, and token values.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit guessed usernames or passwords.
* It must not brute force logout or refresh endpoints.
* It must not reuse tokens against arbitrary endpoints.
* It must not change token claims.
* It must not use new refresh output beyond confirming issuance.
* It must not test real user tokens unless explicitly scoped.
* It must not continue after WAF, abuse detection, lockout, or `429`.
* It must not store raw tokens in findings.
* It must not send token evidence to an LLM.
* It must not classify cookie-only session reuse here; use spec 3.7.

## Test fixtures

Use the synthetic fixture slug: `jwt-session-fixture`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/logout-token/access-vulnerable/login` + `/logout-token/access-vulnerable/logout` + `/logout-token/access-vulnerable/me` | Access token still works after logout. | `confirmed`, `high` |
| `/logout-token/access-safe/login` + `/logout-token/access-safe/logout` + `/logout-token/access-safe/me` | Access token is rejected after logout. | `rejected`, `high` |
| `/logout-token/refresh-vulnerable/login` + `/logout-token/refresh-vulnerable/logout` + `/logout-token/refresh-vulnerable/refresh` | Old refresh token issues new token after logout. | `confirmed`, `high` when refresh test enabled |
| `/logout-token/refresh-safe/login` + `/logout-token/refresh-safe/logout` + `/logout-token/refresh-safe/refresh` | Old refresh token is rejected after logout. | `rejected`, `high` when refresh test enabled |
| `/logout-token/client-clears-only/login` + `/logout-token/client-clears-only/logout` + `/logout-token/client-clears-only/me` | Logout clears token in response but server still accepts old bearer. | `confirmed`, `high` |
| `/logout-token/captcha/login` | Shows CAPTCHA or abuse marker before login. | `stale`, `low`; runner stops |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Safe marker: `/me` returns only synthetic account ID and auth state
* Token store resets between tests

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used for exploratory token discovery only.
* Do not make acceptance depend on live apps unless deterministic token logout fixtures are added.

## Acceptance criteria

The implementation is acceptable when:

* The check is deterministic against the fixture.
* It performs no login unless `allow_login_submission=true`.
* It performs no logout unless `allow_logout_submission=true`.
* It performs no access-token reuse check unless `allow_access_token_reuse_check=true`.
* It performs no refresh-token reuse check unless `allow_refresh_token_reuse_check=true`.
* It completes within the configured request, login, logout, and token-reuse budgets.
* It handles missing tokens, missing logout flows, missing safe markers, malformed JWTs, opaque tokens, redirects, TLS failures, timeouts, and connection errors gracefully.
* It stops on CAPTCHA, MFA challenge without configured fixture secret, lockout, WAF block, abuse detection, or `429`.
* It redacts credentials, CSRF tokens, authorization headers, and token values.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `candidate`, `rejected`, and `stale` statuses correctly.
* It defines only `TokenAcceptedAfterLogoutSignature` and `TokenAcceptedAfterLogoutFinding` as stub-specific types.
* Unit tests cover token extraction, login/logout flow handling, safe marker comparison, old-token reuse, refresh-token gating, client-clearing-only behavior, redaction, safety aborts, and negative assertions.
* Fixture tests cover access-token vulnerable, access-token safe, refresh-token vulnerable, refresh-token safe, client-clears-only, and CAPTCHA abort.
* AI is not called.
