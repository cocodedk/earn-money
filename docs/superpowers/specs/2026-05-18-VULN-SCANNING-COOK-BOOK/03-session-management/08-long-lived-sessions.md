---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 8
slug: long-lived-sessions
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.8 Long-lived sessions

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

Detect session or authentication tokens with excessive lifetime. The runner cares because long-lived sessions increase the window in which stolen cookies, bearer tokens, refresh tokens, or remembered-login artifacts remain useful.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with redirect, TLS, timeout, and cookie-jar controls.
* `scanner_config`: stub-specific knobs listed below.

Optional inputs:

* `authenticated_context`: existing scoped session from the project runner, if already available.
* `prior_cookie_evidence`: cookie evidence collected by other session checks.
* `prior_token_evidence`: token evidence collected by token-handling checks.
* `persistent_login_allowlist`: cookie or token names intentionally used for remember-me flows.
* `clock`: injectable clock for deterministic tests.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `max_public_requests` | `4` | Maximum unauthenticated requests. |
| `max_authenticated_requests` | `4` | Maximum requests using an existing authenticated context. |
| `follow_redirects` | `true` | Capture redirect-chain cookies and the final response. |
| `max_session_lifetime_minutes` | `1440` | Default primary session threshold: 24 hours. |
| `max_remember_me_lifetime_days` | `30` | Default persistent-login threshold when explicitly allowlisted. |
| `max_refresh_token_lifetime_days` | `30` | Default refresh-token threshold. |
| `decode_jwt_without_verification` | `true` | Decode JWT header/payload only; never verify by guessing keys here. |
| `redact_token_values` | `true` | Cookie and token values must be redacted before logs and findings. |

## Detection logic

Detection is deterministic and based on observed expiry metadata.

### 1. Collect expiry evidence

Allowed unauthenticated requests:

1. `GET /`
2. `HEAD /` only if the shared runner already uses it for header collection.
3. Redirect responses while resolving `/`, up to the shared redirect limit.
4. `GET` a discovered login page when earlier phases already identified one.

Allowed authenticated requests, only when `authenticated_context` already exists:

1. `GET` the authenticated landing page supplied by the shared context.
2. `GET` the current-user/profile endpoint supplied by prior discovery.
3. `GET` one safe page that normally refreshes session cookies.

Collect expiry data from:

* `Set-Cookie` `Expires`
* `Set-Cookie` `Max-Age`
* JWT `exp`, `iat`, and `nbf` claims when the token is already observed in a cookie or authorization-bearing evidence
* Structured auth responses from known fixture adapters, if already captured by the login helper

Do not submit login forms in this spec. Use only an existing authenticated context.

### 2. Classify token kind

Primary session artifacts:

* Framework session cookies such as `PHPSESSID`, `JSESSIONID`, `connect.sid`, `ASP.NET_SessionId`.
* Cookies named `session`, `sid`, `sessionid`, `auth`, or similar.
* JWT access tokens stored in cookies.

Persistent-login artifacts:

* Names containing `remember`, `remember_me`, `persistent`, or `device`.
* Tokens explicitly configured in `persistent_login_allowlist`.

Refresh-token artifacts:

* Names containing `refresh`.
* JWTs or opaque tokens returned in a field named `refresh_token`.

Usually out of scope:

* Analytics, consent, locale, theme, experiment, or preference cookies.
* CSRF helper cookies that are not authenticators.
* Load balancer affinity cookies unless project policy treats them as sensitive.

### 3. Calculate lifetime

For cookies:

* Prefer `Max-Age` when present.
* Otherwise use `Expires - observed_at`.
* If neither exists, classify as browser-session scoped and do not flag as long-lived.
* If both exist and conflict, record the conflict and use `Max-Age` for browser behavior.

For JWTs:

* Decode header and payload without verifying the signature.
* Use `exp - iat` when both are present.
* Use `exp - observed_at` when `iat` is missing.
* Do not infer lifetime when `exp` is missing; that belongs to spec 3.11.
* Do not crack or guess signing keys; weak signing keys belong to spec 3.10.

### 4. Classify long lifetime

| Observation | Status | Confidence |
| ----------- | ------ | ---------- |
| Primary session cookie/token lifetime exceeds `max_session_lifetime_minutes`. | `confirmed` | `high` |
| Primary session cookie/token has a persistent expiry but no authenticated context proves it is primary. | `candidate` | `medium` |
| Refresh token lifetime exceeds `max_refresh_token_lifetime_days`. | `candidate` | `medium` |
| Remember-me token exceeds `max_remember_me_lifetime_days`. | `candidate` | `medium` |
| Cookie is browser-session scoped with no persistent expiry. | `rejected` | `high` |
| JWT has no `exp`; defer missing-expiry handling to spec 3.11. | `rejected` | `high` |
| Previous long-lived finding no longer appears in current evidence. | `stale` | `medium` |

Do not create a finding for:

* Non-sensitive cookies.
* Browser-session cookies with no persistent expiry.
* Allowlisted remember-me cookies within configured lifetime.
* Tokens whose expiry cannot be parsed, unless the parser error itself is relevant evidence for spec 3.11.
* Out-of-scope redirect destinations.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `LongLivedSessionSignature`, `LongLivedSessionFinding`.

### `LongLivedSessionSignature`

```ts
export interface LongLivedSessionSignature {
  signature_id: string;
  artifact_name_pattern: string;
  match_type: "equals" | "contains" | "regex";
  artifact_kind:
    | "primary_session_cookie"
    | "access_token"
    | "refresh_token"
    | "remember_me"
    | "unknown_auth_artifact";
  max_lifetime_seconds: number;
  allowlisted_persistent_login: boolean;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `LongLivedSessionFinding`

```ts
export interface LongLivedSessionFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  artifact_name: string;
  artifact_value_fingerprint?: string;
  artifact_kind:
    | "primary_session_cookie"
    | "access_token"
    | "refresh_token"
    | "remember_me"
    | "unknown_auth_artifact";

  source_url: string;
  source_method: "GET" | "HEAD";
  source_status_code: number;
  source_context: "public" | "authenticated" | "redirect" | "prior_evidence";

  observed_expiry: {
    expires_at?: string;
    max_age_seconds?: number;
    jwt_iat?: number;
    jwt_nbf?: number;
    jwt_exp?: number;
    lifetime_seconds?: number;
    threshold_seconds: number;
    browser_session_scoped: boolean;
    expiry_source: "cookie_expires" | "cookie_max_age" | "jwt_exp_iat" | "jwt_exp_observed_at";
  };

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

* Cookie or token name.
* Redacted cookie/token excerpt.
* Observed expiry source and parsed lifetime.
* Source URL and whether evidence was public, authenticated, redirect-chain, or prior evidence.
* Parser error evidence when expiry metadata is malformed.

Recommended remediation:

* Keep primary web sessions short-lived and renew them through explicit idle/absolute timeout policy.
* Use short-lived access tokens and rotate refresh tokens.
* Limit remember-me cookies to a documented lifetime and bind them to device/session metadata.
* Revoke persistent tokens on logout, password change, MFA reset, and account recovery.

## Safety

This check is passive and read-only unless the shared runner supplies an already-authenticated context.

Allowed:

* `GET`
* `HEAD`
* Following redirects within configured limits
* Reading `Set-Cookie` and already-captured auth response evidence
* Decoding JWT header and payload without verifying or modifying the token
* Using an existing authenticated session to visit safe read-only pages

Not allowed:

* Login attempts created by this spec
* Logout requests
* Token refresh requests created by this spec
* JWT signing-key guessing
* Token replay or reuse tests
* Modifying token claims
* Calling external vulnerability databases
* Treating missing JWT `exp` as this finding; use spec 3.11

PII and secrets:

* Never log raw cookie, access-token, refresh-token, or JWT values.
* Redact authorization headers and token-bearing response fields.
* Store token fingerprints only with the project-approved secret hashing helper.
* Do not send token evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Expiry parsing and lifetime comparison are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It parses cookie `Max-Age` and `Expires`.
* It prefers `Max-Age` over `Expires` when both are present.
* It treats cookies without `Max-Age` or `Expires` as browser-session scoped.
* It decodes JWT `exp` and `iat` without verifying or modifying the token.
* It detects a primary session cookie with `Max-Age=2592000` as long-lived under the default 24-hour threshold.
* It detects a JWT access token with `exp - iat` greater than `max_session_lifetime_minutes`.
* It treats missing JWT `exp` as out of scope for this spec.
* It respects `persistent_login_allowlist` and the remember-me threshold.
* It redacts cookie and token values in logs and findings.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit login forms.
* It must not call logout.
* It must not refresh tokens.
* It must not replay tokens.
* It must not crack or guess JWT signing keys.
* It must not modify token claims.
* It must not flag non-sensitive analytics, consent, locale, theme, or preference cookies by default.
* It must not store raw cookie or token values.
* It must not send token evidence to an LLM.
* It must not fail the whole scan when no cookies or tokens are observed.

## Test fixtures

Use the synthetic fixture slug: `session-token-lifetime`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/lifetime/session-cookie-long` | Sets `sid=value; Max-Age=2592000; Path=/; Secure; HttpOnly` | `confirmed`, `high` |
| `/lifetime/session-cookie-short` | Sets `sid=value; Max-Age=1800; Path=/; Secure; HttpOnly` | `rejected`, `high` or no finding |
| `/lifetime/session-cookie-browser` | Sets `sid=value; Path=/; Secure; HttpOnly` | no long-lived finding |
| `/lifetime/expires-long` | Sets `sid` with `Expires` 90 days in the future | `confirmed`, `high` |
| `/lifetime/max-age-wins` | Sets conflicting `Max-Age=1800` and long `Expires` | no long-lived finding |
| `/lifetime/jwt-access-long` | Returns or sets JWT access token with 7-day lifetime | `confirmed`, `high` |
| `/lifetime/jwt-missing-exp` | Returns or sets JWT without `exp` | no finding here; covered by spec 3.11 |
| `/lifetime/remember-allowlisted` | Sets allowlisted remember-me cookie within threshold | no finding |
| `/lifetime/remember-too-long` | Sets remember-me cookie beyond threshold | `candidate`, `medium` |

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used for exploratory cookie/token lifetime observations.
* Do not make acceptance depend on live fixture lifetimes that may vary by version or deployment config.

## Acceptance criteria

The implementation is acceptable when:

* The check is idempotent and read-only.
* The default unauthenticated scan sends no more than `max_public_requests`.
* The authenticated scan uses only an existing authenticated context and sends no more than `max_authenticated_requests`.
* It completes within the Phase 3 request budget.
* It handles no-cookie and no-token responses without errors.
* It handles malformed cookie expiry and malformed JWTs without crashing.
* It handles clock injection for deterministic tests.
* It handles redirects and records which response set the cookie/token.
* It redacts cookie and token values consistently in logs, evidence excerpts, and findings.
* It produces deterministic statuses and confidence values.
* It stores findings with at least one evidence ID.
* It defines only `LongLivedSessionSignature` and `LongLivedSessionFinding` as stub-specific types.
* Unit tests cover cookie expiry parsing, `Max-Age` precedence, browser-session cookies, JWT expiry parsing, missing `exp` deferral, remember-me allowlist behavior, threshold configuration, redaction, stale handling, and negative assertions.
* Fixture tests cover long session cookie, short session cookie, browser-session cookie, long `Expires`, `Max-Age` precedence, long JWT, missing JWT `exp`, allowlisted remember-me, and excessive remember-me lifetime.
* AI is not called.
