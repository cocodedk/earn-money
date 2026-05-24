---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 13
slug: refresh-token-abuse
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.13 Refresh token abuse

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

Detect refresh-token flows that allow token replay, fail to rotate refresh tokens, or fail to invalidate token families after reuse. The runner cares because refresh tokens can mint new access tokens long after the original access token expires, so weak refresh lifecycle controls can extend account compromise.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar and header controls.
* `scanner_config`: stub-specific knobs listed below.

Required for confirmed testing:

* `test_account`: scoped credentials from fixture config, scan config, or approved credential store.
* `login_flow`: known safe login flow that returns a refresh token or token cookie.
* `refresh_flow`: known refresh endpoint and request shape.
* `safe_token_check`: endpoint that proves access-token-authenticated state without exposing sensitive data.

Optional inputs:

* `logout_flow`: known logout URL/API for cleanup.
* `csrf_extractor`: shared helper when token flows require CSRF.
* `token_family_policy`: configured expectations for refresh-token rotation and reuse detection.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled with scoped credentials. |
| `allow_refresh_submission` | `false` | Must be explicitly enabled for refresh testing. |
| `allow_old_refresh_reuse_check` | `false` | Must be explicitly enabled to replay the previous refresh token once. |
| `allow_family_invalidation_check` | `false` | Disabled by default; checks whether reuse invalidates the token family. |
| `max_login_attempts` | `1` | Prevents account lockout and noisy auth logs. |
| `max_refresh_requests` | `3` | Hard cap for refresh-flow requests. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `redact_token_values` | `true` | Token values must be redacted before logs and findings. |

## Detection logic

Detection is deterministic and uses a scoped account plus a known refresh endpoint.

### 1. Obtain initial token pair

Only run when `allow_login_submission=true` and scoped credentials are available.

1. Create a fresh isolated client.
2. Perform one known safe login.
3. Capture access token and refresh token from response body, cookies, or headers.
4. Confirm access token works against `safe_token_check`.
5. Store token fingerprints only.

Do not continue if a refresh token cannot be identified.

### 2. Submit one refresh request

Only run when `allow_refresh_submission=true` and `refresh_flow` is known.

1. Submit the original refresh token to the known refresh endpoint.
2. Capture whether a new access token is issued.
3. Capture whether a new refresh token is issued.
4. Confirm the new access token only against `safe_token_check`.

Expected safe behavior:

* Refresh token rotates, issuing a new refresh token.
* Old refresh token becomes invalid immediately after use.
* Access token is short-lived and separate from refresh-token state.

Candidate weak behavior:

* Same refresh token is returned again.
* New access token is issued but no new refresh token is issued.
* Refresh endpoint accepts missing or malformed client binding metadata when policy requires binding.

### 3. Old refresh-token reuse check

Only run when `allow_old_refresh_reuse_check=true`.

1. Replay the original refresh token once after it has already been used.
2. Do not use any token issued by this replay beyond recording whether issuance happened.
3. Classify whether replay was accepted or rejected.

Confirmed vulnerable if the old refresh token issues a new access token or refresh token after it should have rotated.

### 4. Optional token-family invalidation check

Only run when `allow_family_invalidation_check=true` and fixture/program policy explicitly expects family invalidation.

After old-token reuse is detected or attempted:

1. Try the latest legitimate refresh token once.
2. Confirm whether the token family was invalidated after reuse.
3. Do not use any newly issued tokens beyond recording issuance.

This is optional because family-invalidation policies vary by application. Lack of family invalidation is not always a vulnerability unless the product claims reuse detection.

### 5. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Old refresh token can be reused after rotation to issue new token material. | `confirmed` | `high` |
| Refresh endpoint returns the same refresh token instead of rotating, and policy requires rotation. | `candidate` | `medium` |
| Refresh endpoint issues a new access token but no replacement refresh token, and policy requires refresh-token rotation. | `candidate` | `medium` |
| Reuse is accepted and configured family-invalidation policy is bypassed. | `confirmed` | `high` |
| Old refresh token is rejected after first use. | `rejected` | `high` |
| Test aborted because credentials, token pair, refresh flow, rate limit, or safety precondition is missing. | `stale` | `low` |

Do not run high-volume refresh loops. Do not perform password guessing or account takeover flows.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `RefreshTokenAbuseSignature`, `RefreshTokenAbuseFinding`.

### `RefreshTokenAbuseSignature`

```ts
export interface RefreshTokenAbuseSignature {
  signature_id: string;
  refresh_url: string;
  refresh_method: "POST";
  token_carrier: "authorization_header" | "cookie" | "json_body";
  abuse_kind:
    | "no_rotation"
    | "old_refresh_reuse"
    | "family_invalidation_bypass";
  requires_valid_credentials: true;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `RefreshTokenAbuseFinding`

```ts
export interface RefreshTokenAbuseFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  login_url: string;
  refresh_url: string;
  safe_check_url: string;
  token_carrier: "authorization_header" | "cookie" | "json_body";

  original_refresh_fingerprint: string;
  first_refresh_response: {
    status_code: number;
    issued_access_token: boolean;
    issued_refresh_token: boolean;
    new_refresh_fingerprint?: string;
    same_refresh_returned: boolean;
  };

  reuse_response?: {
    status_code: number;
    issued_access_token: boolean;
    issued_refresh_token: boolean;
    token_error_code?: string;
  };

  family_invalidation_response?: {
    status_code: number;
    latest_refresh_still_accepted: boolean;
    token_error_code?: string;
  };

  abuse_kind:
    | "no_rotation"
    | "old_refresh_reuse"
    | "family_invalidation_bypass";

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
* Initial token capture evidence with redacted values.
* First refresh request/response evidence.
* Old refresh-token reuse evidence when enabled.
* Optional family-invalidation evidence when enabled.
* Safe token check evidence for newly issued access token.

Recommended remediation:

* Rotate refresh tokens on every use.
* Reject old refresh tokens immediately after rotation.
* Invalidate the token family when reuse of an old refresh token is detected, if that is the product policy.
* Bind refresh tokens to client/device metadata where appropriate.
* Revoke refresh tokens on logout, password change, MFA reset, account recovery, and suspicious reuse.

## Safety

This check is active because it logs in and submits refresh requests.

Allowed:

* One valid login request when `allow_login_submission=true`.
* One normal refresh request when `allow_refresh_submission=true`.
* One old-token reuse request when `allow_old_refresh_reuse_check=true`.
* One optional family-invalidation request when `allow_family_invalidation_check=true`.
* Safe access-token check against `safe_token_check`.

Not allowed:

* Password guessing.
* Username guessing.
* Discovering or brute forcing refresh endpoints.
* High-volume refresh loops.
* Concurrent refresh checks; those belong to race-condition testing unless a separate approved plan scopes them here.
* Using newly issued tokens beyond safe-marker verification.
* Changing token claims.
* Testing real user tokens not explicitly scoped.
* Continuing after WAF, abuse detection, lockout, or `429`.

PII and secrets:

* Never log passwords, CSRF tokens, authorization headers, or raw token values.
* Redact usernames/emails unless fixture-only synthetic identifiers are used.
* Store token fingerprints only with the project-approved secret hashing helper.
* Do not send token evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Refresh request sequencing and response classification are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It uses isolated clients for token lifecycle tests.
* It captures and fingerprints refresh tokens without logging raw values.
* It submits only a known refresh flow.
* It confirms the initial access token works against `safe_token_check`.
* It detects when the first refresh returns the same refresh token.
* It detects when the first refresh issues a new access token but no replacement refresh token while policy requires refresh-token rotation.
* It detects when the original refresh token can be reused once after rotation.
* It creates a `confirmed`, `high` finding when old refresh-token reuse issues new token material.
* It creates a `candidate`, `medium` finding when refresh does not rotate and policy requires rotation.
* It creates a `rejected`, `high` result or no vulnerability finding when old refresh tokens are rejected.
* It respects all refresh-request budgets.
* It redacts credentials, CSRF tokens, authorization headers, and token values.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit guessed usernames or passwords.
* It must not brute force refresh endpoints.
* It must not run high-volume refresh loops.
* It must not run concurrent refresh checks from this spec.
* It must not use newly issued tokens beyond safe-marker verification.
* It must not change token claims.
* It must not test real user tokens unless explicitly scoped.
* It must not continue after WAF, abuse detection, lockout, or `429`.
* It must not store raw tokens in findings.
* It must not send token evidence to an LLM.

## Test fixtures

Use the synthetic fixture slug: `jwt-session-fixture`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/refresh/no-rotation/login` + `/refresh/no-rotation/refresh` | Refresh returns the same refresh token. | `candidate`, `medium` |
| `/refresh/no-replacement-refresh/login` + `/refresh/no-replacement-refresh/refresh` | Refresh issues a new access token but no replacement refresh token while policy requires rotation. | `candidate`, `medium` |
| `/refresh/reuse-vulnerable/login` + `/refresh/reuse-vulnerable/refresh` | First refresh rotates, but original refresh token can be reused. | `confirmed`, `high` |
| `/refresh/reuse-safe/login` + `/refresh/reuse-safe/refresh` | First refresh rotates and original refresh token is rejected. | `rejected`, `high` |
| `/refresh/family-bypass/login` + `/refresh/family-bypass/refresh` | Old-token reuse is detected but latest token still works despite configured family invalidation. | `confirmed`, `high` when family check enabled |
| `/refresh/no-refresh-token/login` | Login issues only access token. | `stale`, `low` or no finding |
| `/refresh/rate-limited/login` + `/refresh/rate-limited/refresh` | Refresh flow returns rate-limit or abuse marker. | `stale`, `low`; runner stops |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Safe marker: `/me` returns only synthetic account ID and auth state
* Token store resets between tests

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used for exploratory token discovery only.
* Do not make acceptance depend on live apps unless deterministic refresh-token fixtures are added.

## Acceptance criteria

The implementation is acceptable when:

* The check is deterministic against the fixture.
* It performs no login unless `allow_login_submission=true`.
* It performs no refresh unless `allow_refresh_submission=true`.
* It performs no old-token reuse check unless `allow_old_refresh_reuse_check=true`.
* It performs no family-invalidation check unless `allow_family_invalidation_check=true`.
* It completes within the configured login and refresh budgets.
* It handles missing refresh tokens, missing refresh flows, malformed JWTs, opaque tokens, redirects, TLS failures, timeouts, and connection errors gracefully.
* It stops on CAPTCHA, MFA challenge without configured fixture secret, lockout, WAF block, abuse detection, or `429`.
* It redacts credentials, CSRF tokens, authorization headers, and token values.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `candidate`, `rejected`, and `stale` statuses correctly.
* It defines only `RefreshTokenAbuseSignature` and `RefreshTokenAbuseFinding` as stub-specific types.
* Unit tests cover token extraction, refresh request shaping, first-refresh classification, missing replacement refresh token, old-token reuse gating, family-invalidation gating, safe marker verification, redaction, safety aborts, and negative assertions.
* Fixture tests cover no rotation, no replacement refresh token, old-token reuse vulnerable, old-token reuse safe, family-invalidation bypass, no refresh token, and rate-limit abort.
* AI is not called.
