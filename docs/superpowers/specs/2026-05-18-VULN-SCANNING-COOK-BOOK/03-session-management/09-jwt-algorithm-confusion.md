---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 9
slug: jwt-algorithm-confusion
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.9 JWT algorithm confusion

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

Detect JWT validation behavior that trusts attacker-controlled `alg` headers, accepts unsigned tokens, or confuses asymmetric and symmetric signing algorithms. The runner cares because algorithm confusion can let an attacker forge tokens without knowing the intended private signing key.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar and header controls.
* `scanner_config`: stub-specific knobs listed below.

Optional inputs:

* `authenticated_context`: existing scoped session that already contains an access token or JWT cookie.
* `test_account`: scoped credentials from fixture config or approved credential store, only when active token submission is enabled.
* `login_flow`: known safe login flow, only when a token must be obtained by the runner.
* `safe_authenticated_check`: endpoint that proves authenticated state without exposing sensitive data.
* `jwks_urls`: discovered or configured in-scope JWKS URLs.
* `prior_token_evidence`: JWTs discovered by earlier checks.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled if the runner needs to obtain a JWT. |
| `allow_modified_token_submission` | `false` | Must be explicitly enabled for active algorithm-confusion probes. |
| `allow_jwks_fetch` | `true` | Allows read-only fetch of same-origin or configured JWKS. |
| `max_modified_token_requests` | `2` | Bounded active probes against the safe marker. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `follow_redirects` | `false` | Keep safe-marker redirects visible as evidence. |
| `redact_token_values` | `true` | JWT values must be redacted before logs and findings. |

Default mode is passive. It decodes JWT headers and payloads without verification and does not submit modified tokens.

## Detection logic

Detection is deterministic. Active probes are allowed only against scoped fixtures or explicitly authorized targets.

### 1. Collect JWT evidence

Sources:

* `Authorization: Bearer <jwt>` from existing authenticated context.
* Cookie values that parse as JWTs.
* Auth responses already captured by shared login helpers.
* Prior token evidence from session/token checks.

JWT shape:

```text
base64url(header).base64url(payload).base64url(signature)
```

Decode header and payload without verifying the signature. Never log the raw token.

Collect:

* header `alg`
* header `typ`
* header `kid`
* payload `iss`, `aud`, `sub` fingerprint, `iat`, `nbf`, `exp`
* token source, such as cookie name or authorization header
* whether the token was observed in a public or authenticated context

### 2. Passive header classification

Passive findings:

| Observation | Status | Confidence |
| ----------- | ------ | ---------- |
| Server-issued JWT uses `alg: none` and has no signature. | `confirmed` | `high` |
| Server-issued JWT uses `alg: none` with a signature-like third segment. | `candidate` | `medium` |
| Server-issued JWT uses an unexpected weak algorithm from config, such as `HS256` where only asymmetric algorithms are expected. | `candidate` | `medium` |
| Token header has missing or malformed `alg`. | `candidate` | `low` |
| Token uses configured allowed algorithms only. | `rejected` | `high` |

Passive decoding cannot prove that modified tokens are accepted. It only identifies risky issued-token characteristics.

### 3. Active `alg=none` probe

Only run when `allow_modified_token_submission=true`, a scoped token exists, and `safe_authenticated_check` is configured.

1. Take the scoped JWT.
2. Decode header and payload.
3. Preserve payload claims exactly; do not change `sub`, `role`, `scope`, `aud`, `iss`, or expiry.
4. Create a modified token with header `alg: none` and an empty signature.
5. Submit the modified token only to `safe_authenticated_check`.
6. Compare response to the baseline valid-token response.

Confirmed vulnerable if the safe marker accepts the unsigned token as authenticated.

Do not attempt privilege escalation by changing claims. Claim-tampering belongs to access-control and API-authorization specs.

### 4. Active asymmetric/symmetric confusion probe

Only run when all conditions are true:

* `allow_modified_token_submission=true`.
* The original token uses an asymmetric algorithm such as `RS256`, `RS384`, `RS512`, `ES256`, `ES384`, or `ES512`.
* A public key or JWKS is available from a same-origin or configured in-scope URL.
* The fixture or target explicitly permits this probe.

Probe:

1. Preserve the payload exactly.
2. Change header `alg` to the matching HMAC family, usually `HS256`.
3. Sign with the public key material as the HMAC secret, using deterministic library behavior.
4. Submit only to `safe_authenticated_check`.

Confirmed vulnerable if the safe marker accepts the HS-signed token where the server should require the asymmetric algorithm.

Do not brute force keys, do not use external JWKS URLs, and do not mutate claims.

### 5. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Modified `alg=none` token is accepted by the safe marker. | `confirmed` | `high` |
| HS-signed token using public key material is accepted by the safe marker. | `confirmed` | `high` |
| Server-issued token uses `alg=none`. | `confirmed` | `high` |
| Passive evidence suggests unexpected algorithm but no active probe ran. | `candidate` | `medium` |
| Modified token is rejected while valid baseline token is accepted. | `rejected` | `high` |
| Test aborted because token, safe marker, JWKS, credentials, or authorization for active probing is missing. | `stale` | `low` |

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `JwtAlgorithmConfusionSignature`, `JwtAlgorithmConfusionFinding`.

### `JwtAlgorithmConfusionSignature`

```ts
export interface JwtAlgorithmConfusionSignature {
  signature_id: string;
  algorithm: string;
  probe_kind:
    | "passive_none"
    | "passive_unexpected_algorithm"
    | "active_none_acceptance"
    | "active_asymmetric_symmetric_confusion";
  expected_algorithms: string[];
  requires_modified_token_submission: boolean;
  requires_jwks: boolean;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `JwtAlgorithmConfusionFinding`

```ts
export interface JwtAlgorithmConfusionFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  token_source: "authorization_header" | "cookie" | "auth_response" | "prior_evidence";
  token_name?: string;
  token_fingerprint: string;
  safe_check_url?: string;

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
    exp?: number;
  };

  probe_result: {
    probe_kind:
      | "passive_none"
      | "passive_unexpected_algorithm"
      | "active_none_acceptance"
      | "active_asymmetric_symmetric_confusion";
    modified_token_submitted: boolean;
    claims_modified: false;
    baseline_status_code?: number;
    modified_status_code?: number;
    accepted_modified_token: boolean;
    jwks_url?: string;
  };

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
* Baseline safe-marker response when active probing is used.
* Modified-token safe-marker response when active probing is used.
* JWKS/public-key evidence when asymmetric/symmetric confusion is tested.

Recommended remediation:

* Enforce a server-side allowlist of expected algorithms.
* Reject `alg=none` for authenticated tokens.
* Do not choose verification algorithm solely from the token header.
* Keep symmetric and asymmetric verification code paths separate.
* Validate `iss`, `aud`, `exp`, `nbf`, and key ID according to issuer policy.

## Safety

Passive JWT decoding is read-only. Active modified-token submission is potentially exploit-like and must be explicitly enabled.

Allowed by default:

* Decode JWT header and payload without verification.
* Fetch same-origin or configured JWKS when `allow_jwks_fetch=true`.
* Read token metadata from existing authenticated context or prior evidence.

Allowed only when explicitly enabled:

* One login request to obtain a scoped token.
* At most `max_modified_token_requests` modified-token requests.
* Submitting modified tokens only to `safe_authenticated_check`.

Not allowed:

* Claim escalation.
* Changing `sub`, `role`, `scope`, `aud`, `iss`, or expiry.
* Token replay against arbitrary endpoints.
* Brute-forcing signing keys.
* Using external or out-of-scope JWKS URLs.
* Trying large algorithm matrices.
* Testing real user tokens not explicitly scoped.
* Continuing after WAF, lockout, abuse detection, or `429`.

PII and secrets:

* Never log raw JWTs.
* Redact authorization headers and token-bearing cookies.
* Store token fingerprints only with the project-approved secret hashing helper.
* Store subject as a fingerprint, not raw identifier, unless fixture-only.
* Do not send token evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. JWT parsing, token construction, and response comparison are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It decodes JWT header and payload without logging raw tokens.
* It creates a `confirmed`, `high` finding for a server-issued unsigned JWT with `alg=none`.
* It creates a `candidate`, `medium` finding for unexpected algorithms when no active probe is allowed.
* It submits no modified tokens when `allow_modified_token_submission=false`.
* It preserves payload claims exactly during active probes.
* It submits modified tokens only to `safe_authenticated_check`.
* It confirms `alg=none` acceptance only when the modified unsigned token authenticates successfully.
* It confirms asymmetric/symmetric confusion only when the HS-signed token using public key material authenticates successfully.
* It rejects the finding when the valid baseline token works and the modified token fails.
* It redacts token values and authorization headers.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not change user, role, scope, audience, issuer, or expiry claims.
* It must not brute-force signing keys.
* It must not use out-of-scope JWKS URLs.
* It must not submit modified tokens to arbitrary endpoints.
* It must not run active probes without explicit enablement.
* It must not use real user tokens unless explicitly scoped.
* It must not continue after WAF, abuse detection, lockout, or `429`.
* It must not store raw JWTs in findings.
* It must not send token evidence to an LLM.
* It must not mark passive unexpected algorithm evidence as confirmed acceptance.

## Test fixtures

Use the synthetic fixture slug: `jwt-session-fixture`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/jwt/none-issued` | Issues unsigned `alg=none` token. | `confirmed`, `high` passive finding |
| `/jwt/none-accepts/login` + `/jwt/none-accepts/me` | Issues normal JWT but accepts modified `alg=none` token at `/me`. | `confirmed`, `high` when active probes enabled |
| `/jwt/none-rejects/login` + `/jwt/none-rejects/me` | Rejects modified `alg=none` token. | `rejected`, `high` |
| `/jwt/rs256-hs256-confusion/login` + `/jwt/rs256-hs256-confusion/jwks.json` + `/jwt/rs256-hs256-confusion/me` | Accepts HS256 token signed with public key material. | `confirmed`, `high` when active probes enabled |
| `/jwt/rs256-safe/login` + `/jwt/rs256-safe/jwks.json` + `/jwt/rs256-safe/me` | Rejects HS256 confusion token. | `rejected`, `high` |
| `/jwt/unexpected-alg` | Issues token using algorithm outside configured allowlist. | `candidate`, `medium` |
| `/jwt/malformed` | Provides malformed JWT-like value. | no crash; `stale` or no finding |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Safe marker: `/me` returns only synthetic account ID and auth state

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used for exploratory token discovery only.
* Do not make acceptance depend on live apps unless a deterministic JWT fixture adapter is added.

## Acceptance criteria

The implementation is acceptable when:

* Passive mode is idempotent and read-only.
* Active mode runs only when explicitly enabled.
* Active mode submits no more than `max_modified_token_requests`.
* It handles missing tokens, malformed JWTs, missing JWKS, invalid base64url, redirects, TLS failures, timeouts, and connection errors gracefully.
* It preserves claims exactly in modified-token probes.
* It compares valid-token baseline and modified-token response deterministically.
* It redacts tokens and authorization headers consistently in logs, evidence excerpts, and findings.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `candidate`, `rejected`, and `stale` statuses correctly.
* It defines only `JwtAlgorithmConfusionSignature` and `JwtAlgorithmConfusionFinding` as stub-specific types.
* Unit tests cover JWT parsing, `alg=none` passive detection, modified unsigned-token construction, claim-preservation checks, JWKS handling, HS/RS confusion token construction, active-probe gating, response classification, redaction, and negative assertions.
* Fixture tests cover issued `alg=none`, active `alg=none` acceptance, active `alg=none` rejection, HS/RS confusion acceptance, HS/RS rejection, unexpected algorithm, and malformed token handling.
* AI is not called.
