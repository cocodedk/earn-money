---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 11
slug: missing-expiry
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.11 Missing expiry

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

Detect authentication tokens that do not carry an enforceable expiration indicator, especially JWTs missing the `exp` claim. The runner cares because tokens without expiry may remain valid until manually revoked, increasing the impact of token theft and making session lifetime policy hard to enforce.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client used only for read-only token collection when needed.
* `scanner_config`: stub-specific knobs listed below.

Optional inputs:

* `authenticated_context`: existing scoped session that already contains JWTs or token-bearing responses.
* `prior_token_evidence`: JWTs or auth responses discovered by earlier checks.
* `test_account`: scoped credentials, only when token collection by login is explicitly enabled.
* `login_flow`: known safe login flow, only when a token must be obtained by the runner.
* `token_expiry_policy`: project-configured expectations per token kind.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled if the runner needs to obtain a token. |
| `request_timeout_ms` | `10000` | Per-request timeout for token collection only. |
| `decode_jwt_without_verification` | `true` | Decode JWT header/payload only; never verify by guessing keys here. |
| `treat_missing_exp_as_confirmed` | `true` | Missing `exp` on access/session JWTs is confirmed by token structure. |
| `flag_missing_nbf_or_iat` | `false` | Optional hardening check; disabled by default. |
| `redact_token_values` | `true` | Token values must be redacted before logs and findings. |

## Detection logic

Detection is deterministic and passive after token collection.

### 1. Collect token evidence

Sources:

* `Authorization: Bearer <jwt>` from existing authenticated context.
* Cookie values that parse as JWTs.
* Auth responses already captured by shared login helpers.
* Prior token evidence from session/token checks.

Only submit login when `allow_login_submission=true`, scoped credentials are available, and a known safe login flow is configured. Do not perform token refresh in this spec.

### 2. Decode JWT metadata

Decode JWT header and payload without verifying the signature. This spec does not test signing strength or algorithm confusion.

Collect:

* header `alg`, `typ`, `kid`
* payload `iss`, `aud`, `sub` fingerprint
* payload `iat`, `nbf`, `exp`
* token source and token kind

Token kinds:

* `access_token`
* `id_token`
* `session_jwt`
* `refresh_token`
* `unknown_jwt`

Classify by name, source, and response field. If a token is opaque and not decodable, do not infer missing expiry from the value alone.

### 3. Classify missing expiry

| Observation | Status | Confidence |
| ----------- | ------ | ---------- |
| Access/session JWT lacks `exp`. | `confirmed` | `high` |
| ID token lacks `exp`. | `confirmed` | `high` |
| Refresh JWT lacks `exp` and policy requires explicit refresh expiry. | `confirmed` | `high` |
| Refresh JWT lacks `exp` and policy is absent or allows server-side refresh expiry. | `candidate` | `medium` |
| JWT has malformed or non-numeric `exp`. | `confirmed` | `medium` |
| JWT has `exp`, but lifetime is too long; defer excessive-lifetime handling to spec 3.8. | `rejected` | `high` |
| Opaque token has no visible expiry metadata. | `rejected` | `high` |
| Browser session cookie lacks `Expires`/`Max-Age`. | `rejected` | `high` |
| JWT includes valid numeric `exp`. | `rejected` | `high` |
| Previous missing-expiry finding no longer appears in current evidence. | `stale` | `medium` |

Optional hardening:

* If `flag_missing_nbf_or_iat=true`, missing `iat` or `nbf` may be recorded as low-confidence hardening candidates.
* Do not mix those candidates with the main missing-`exp` finding unless the project schema supports sub-issues.

### 4. Boundaries

Do not create a finding for:

* Browser-session cookies without persistent expiry.
* Opaque tokens where expiry is server-side and not observable.
* JWTs whose `exp` exists but exceeds policy; use spec 3.8.
* JWTs accepted after logout; use spec 3.12.
* Weak signing keys; use spec 3.10.
* Algorithm confusion; use spec 3.9.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `MissingExpirySignature`, `MissingExpiryFinding`.

### `MissingExpirySignature`

```ts
export interface MissingExpirySignature {
  signature_id: string;
  token_kind:
    | "access_token"
    | "id_token"
    | "session_jwt"
    | "refresh_token"
    | "unknown_jwt";
  required_claim: "exp";
  optional_claims?: Array<"iat" | "nbf">;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `MissingExpiryFinding`

```ts
export interface MissingExpiryFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  token_source: "authorization_header" | "cookie" | "auth_response" | "prior_evidence";
  token_name?: string;
  token_fingerprint: string;
  token_kind:
    | "access_token"
    | "id_token"
    | "session_jwt"
    | "refresh_token"
    | "unknown_jwt";

  observed_header: {
    alg?: string;
    typ?: string;
    kid?: string;
  };

  observed_payload: {
    iss?: string;
    aud?: string | string[];
    sub_fingerprint?: string;
    iat?: number;
    nbf?: number;
    exp_present: boolean;
    exp_value_type?: "number" | "string" | "null" | "missing" | "other";
  };

  expiry_issue:
    | "missing_exp"
    | "malformed_exp"
    | "missing_iat_hardening"
    | "missing_nbf_hardening";

  title: string;
  summary: string;
  remediation: {
    summary: string;
    steps: string[];
  };

  confidence: "low" | "medium" | "high";
  status: "candidate" | "confirmed" | "rejected" | "stale";
  safe: boolean;
  created_at: string;
  updated_at: string;
}
```

Evidence requirements:

* Redacted token source and token fingerprint.
* Decoded JWT header and non-sensitive payload metadata.
* Claim presence/type summary.
* Source URL or prior evidence reference.
* `safe=true` only for passive or prior-evidence observations; set `safe=false` when this stub submitted login to collect the token.

Recommended remediation:

* Add a numeric `exp` claim to all access, ID, and session JWTs.
* Enforce expiration server-side during token verification.
* Keep token lifetime policy documented and tested.
* Use short-lived access tokens with refresh-token rotation where appropriate.
* Treat refresh-token lifetime and revocation as separate policy controls.

## Safety

Default behavior is passive after token collection.

Allowed:

* Decode JWT header and payload without verification.
* Read existing authenticated context or prior token evidence.
* Submit one login request only when `allow_login_submission=true` and credentials are scoped.

Not allowed:

* Token refresh requests.
* Logout requests.
* Modified-token submission.
* Token replay tests.
* JWT signing-key guessing.
* Algorithm-confusion probes.
* Inferring missing expiry from opaque token length or randomness.
* Treating browser-session cookies as missing-expiry findings.

PII and secrets:

* Never log raw JWTs.
* Redact authorization headers and token-bearing cookies.
* Store token fingerprints only with the project-approved secret hashing helper.
* Store subject as a fingerprint, not raw identifier, unless fixture-only.
* Do not send token evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. JWT claim parsing and claim-presence checks are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It decodes JWT header and payload without logging raw tokens.
* It detects an access/session JWT with no `exp` as `confirmed`, `high`.
* It detects an ID token with no `exp` as `confirmed`, `high`.
* It detects malformed `exp` values as `confirmed`, `medium`.
* It treats JWTs with valid numeric `exp` as rejected or no finding.
* It defers overly long `exp` lifetimes to spec 3.8.
* It does not infer missing expiry for opaque tokens.
* It redacts token values and authorization headers.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit modified tokens.
* It must not refresh tokens.
* It must not call logout.
* It must not replay tokens.
* It must not crack or guess signing keys.
* It must not perform algorithm-confusion probes.
* It must not flag browser-session cookies that lack `Expires` or `Max-Age`.
* It must not store raw JWTs in findings.
* It must not send token evidence to an LLM.
* It must not fail the whole scan when no tokens are observed.

## Test fixtures

Use the synthetic fixture slug: `jwt-session-fixture`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/jwt/missing-exp-access` | Issues access/session JWT without `exp`. | `confirmed`, `high` |
| `/jwt/missing-exp-id-token` | Issues ID-token-style JWT without `exp`. | `confirmed`, `high` |
| `/jwt/missing-exp-refresh` | Issues refresh JWT without `exp`. | `candidate`, `medium` |
| `/jwt/malformed-exp-string` | Issues JWT with `exp: "never"`. | `confirmed`, `medium` |
| `/jwt/valid-exp` | Issues JWT with numeric `exp`. | `rejected`, `high` or no finding |
| `/jwt/long-exp` | Issues JWT with valid but excessive future `exp`. | no missing-expiry finding; covered by spec 3.8 |
| `/jwt/opaque-token` | Issues opaque token. | no missing-expiry finding |
| `/jwt/browser-session-cookie` | Sets session cookie with no `Expires`/`Max-Age`. | no missing-expiry finding |

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used for exploratory token discovery only.
* Do not make acceptance depend on live apps unless a deterministic JWT fixture adapter is added.

## Acceptance criteria

The implementation is acceptable when:

* Passive mode is idempotent and read-only after token collection.
* It performs no login unless `allow_login_submission=true`.
* It performs no token refresh, logout, replay, or modified-token request.
* It marks findings from passive/prior evidence as `safe=true` and findings from login-submitted token collection as `safe=false`.
* It handles missing tokens, malformed JWTs, invalid base64url, opaque tokens, redirects, TLS failures, timeouts, and connection errors gracefully.
* It redacts tokens and authorization headers consistently in logs, evidence excerpts, and findings.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `candidate`, `rejected`, and `stale` statuses correctly.
* It defines only `MissingExpirySignature` and `MissingExpiryFinding` as stub-specific types.
* Unit tests cover JWT parsing, missing `exp`, malformed `exp`, valid `exp`, long-but-valid `exp` deferral, opaque token deferral, browser-session cookie deferral, optional `iat`/`nbf` hardening, redaction, and negative assertions.
* Fixture tests cover missing access-token expiry, missing ID-token expiry, missing refresh-token expiry, malformed `exp`, valid `exp`, long `exp`, opaque token, and browser-session cookie.
* AI is not called.
