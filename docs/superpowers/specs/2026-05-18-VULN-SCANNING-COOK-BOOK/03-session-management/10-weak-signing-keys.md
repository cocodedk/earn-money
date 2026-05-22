---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 10
slug: weak-signing-keys
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.10 Weak signing keys

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

Detect JWTs or signed session artifacts protected by weak, default, or easily guessable HMAC secrets. The runner cares because a weak signing key lets an attacker forge valid tokens even when the application rejects algorithm-confusion tricks.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client used only for read-only token collection when needed.
* `scanner_config`: stub-specific knobs listed below.

Optional inputs:

* `authenticated_context`: existing scoped session that already contains an HMAC-signed JWT.
* `prior_token_evidence`: JWTs discovered by other token/session checks.
* `test_account`: scoped credentials, only when token collection by login is explicitly enabled.
* `login_flow`: known safe login flow, only when a token must be obtained by the runner.
* `approved_weak_secret_dictionary`: project-approved bounded list of weak/default secrets.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled if the runner needs to obtain a JWT. |
| `allow_offline_weak_secret_check` | `true` | Allows bounded local verification against approved weak secrets. |
| `max_secret_candidates` | `128` | Hard cap for default weak-secret candidates. |
| `allow_large_dictionary_attack` | `false` | Disabled by default; requires explicit authorization and separate plan. |
| `allow_forged_token_submission` | `false` | Disabled by default; not needed to confirm an offline HMAC key match. |
| `request_timeout_ms` | `10000` | Per-request timeout for token collection only. |
| `redact_token_values` | `true` | Token values and recovered secrets must be redacted before logs and findings. |

Default weak-secret candidates should be intentionally small and auditable, for example:

```text
secret
changeme
password
jwtsecret
default
development
test
admin
```

Projects may replace this list with a maintained fixture-safe dictionary. The runner must not silently fall back to large public cracking lists.

## Detection logic

Detection is deterministic and offline by default.

### 1. Collect signed-token evidence

Sources:

* `Authorization: Bearer <jwt>` from existing authenticated context.
* Cookie values that parse as JWTs.
* Auth responses already captured by shared login helpers.
* Prior token evidence from session/token checks.

Decode JWT header and payload without verifying the signature.

Only HMAC-family algorithms are in scope for offline weak-secret checks:

* `HS256`
* `HS384`
* `HS512`

Do not attempt to recover private keys for asymmetric algorithms such as `RS256`, `ES256`, or `EdDSA`. Algorithm confusion is covered by spec 3.9.

### 2. Offline HMAC verification

When `allow_offline_weak_secret_check=true`:

1. Parse the token into signing input and signature.
2. Confirm the header uses an HMAC-family algorithm.
3. For each approved candidate secret up to `max_secret_candidates`, compute the expected HMAC.
4. Compare signatures using constant-time comparison.
5. Stop at the first matching candidate.

A match proves the token was signed with a weak/default candidate. No network request is needed to confirm.

Do not mutate token claims. Do not submit forged tokens by default.

### 3. Optional forged-token verification

This is disabled by default and should not be part of the first implementation.

Only run when:

* `allow_forged_token_submission=true`.
* The target is a fixture or the program explicitly authorizes proof by submission.
* `safe_authenticated_check` is configured in the shared runner context.

The forged token must preserve all original claims exactly and only re-sign with the recovered weak key. It must be submitted only to the safe marker endpoint.

### 4. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Observed HMAC JWT signature validates with an approved weak/default candidate. | `confirmed` | `high` |
| HMAC JWT uses a very short signature key indicator from fixture metadata but no offline match was run. | `candidate` | `low` |
| Token uses HMAC algorithm but no weak candidate matches within budget. | `rejected` | `medium` |
| Token uses asymmetric algorithm. | `rejected` | `high` for this spec |
| Test aborted because token is malformed, dictionary disabled, or candidate budget is exhausted. | `stale` | `low` |

Do not create a finding from algorithm name alone. `HS256` is not automatically weak; the finding requires a weak-key match or explicit fixture metadata.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `WeakSigningKeySignature`, `WeakSigningKeyFinding`.

### `WeakSigningKeySignature`

```ts
export interface WeakSigningKeySignature {
  signature_id: string;
  token_algorithm: "HS256" | "HS384" | "HS512";
  secret_candidate_fingerprint: string;
  secret_candidate_label:
    | "default"
    | "common"
    | "fixture"
    | "project_dictionary";
  candidate_source: "built_in" | "project_config" | "fixture_config";
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `WeakSigningKeyFinding`

```ts
export interface WeakSigningKeyFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  token_source: "authorization_header" | "cookie" | "auth_response" | "prior_evidence";
  token_name?: string;
  token_fingerprint: string;
  token_algorithm: "HS256" | "HS384" | "HS512";

  observed_header: {
    alg: "HS256" | "HS384" | "HS512";
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

  weak_secret_match: {
    candidate_fingerprint: string;
    candidate_label: "default" | "common" | "fixture" | "project_dictionary";
    candidate_index: number;
    total_candidates_tested: number;
    match_confirmed_offline: boolean;
    forged_token_submitted: boolean;
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
* Candidate dictionary metadata: source, count, and candidate fingerprint, not raw secret.
* Offline verification result.
* Optional forged-token safe-marker response only when explicitly enabled.

Recommended remediation:

* Replace weak/default HMAC secrets with high-entropy randomly generated secrets.
* Rotate signing keys and invalidate tokens signed by the old key.
* Store signing secrets in a managed secret store.
* Use separate keys per environment and issuer.
* Consider asymmetric signing with strict algorithm allowlists where operationally appropriate.

## Safety

Default behavior is local and offline after token collection. It does not submit forged tokens.

Allowed by default:

* Decode JWT header and payload without verification.
* Test HMAC signatures locally against an approved bounded weak-secret list.
* Use an existing authenticated context or prior token evidence.

Allowed only when explicitly enabled:

* One login request to obtain a scoped token.
* Large dictionary attacks, under a separate explicit plan and authorization.
* Forged-token submission to a safe marker endpoint.

Not allowed:

* Silent use of public password lists or large dictionaries.
* GPU cracking, distributed cracking, or hashcat-style workflows by default.
* Brute-forcing beyond `max_secret_candidates`.
* Testing real user tokens not explicitly scoped.
* Submitting forged tokens by default.
* Changing claims in a forged token.
* Trying asymmetric private-key recovery.
* Sending tokens or candidate secrets to external services.

PII and secrets:

* Never log raw JWTs.
* Never log recovered secret candidates.
* Redact authorization headers and token-bearing cookies.
* Store token and secret candidate fingerprints only with the project-approved secret hashing helper.
* Do not send token or secret evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. HMAC verification and dictionary matching are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It decodes JWT header and payload without logging raw tokens.
* It restricts default offline checking to HMAC-family algorithms.
* It uses only an approved bounded weak-secret dictionary by default.
* It enforces `max_secret_candidates`.
* It verifies candidate signatures locally using constant-time comparison.
* It creates a `confirmed`, `high` finding when a token validates with a weak candidate.
* It does not require forged-token submission to confirm an offline HMAC match.
* It marks asymmetric algorithms as out of scope for this spec.
* It redacts token values and recovered secrets.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not run large dictionary attacks by default.
* It must not invoke GPU cracking or external cracking services.
* It must not silently use public password lists.
* It must not brute force beyond the configured candidate budget.
* It must not submit forged tokens unless explicitly enabled.
* It must not change claims in any optional forged token.
* It must not attempt asymmetric private-key recovery.
* It must not store raw JWTs or raw recovered secrets.
* It must not send token or secret evidence to an LLM.
* It must not flag `HS256` alone as weak without a matching weak candidate.

## Test fixtures

Use the synthetic fixture slug: `jwt-session-fixture`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/jwt/weak-secret` | Issues `HS256` JWT signed with fixture weak secret from approved dictionary. | `confirmed`, `high` |
| `/jwt/strong-secret` | Issues `HS256` JWT signed with secret not in approved dictionary. | `rejected`, `medium` or no finding |
| `/jwt/hs384-weak-secret` | Issues `HS384` JWT signed with fixture weak secret. | `confirmed`, `high` |
| `/jwt/hs512-weak-secret` | Issues `HS512` JWT signed with fixture weak secret. | `confirmed`, `high` |
| `/jwt/rs256-token` | Issues `RS256` JWT. | out of scope for this spec; no weak-secret finding |
| `/jwt/malformed` | Provides malformed JWT-like value. | no crash; `stale` or no finding |
| `/jwt/forged-submission-safe` | Fixture accepts token re-signed with recovered weak key and unchanged claims. | optional active proof when enabled |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Weak secret: fixture-provided value from approved test dictionary
* Safe marker: `/me` returns only synthetic account ID and auth state

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used for exploratory token discovery only.
* Do not make acceptance depend on live apps unless a deterministic JWT fixture adapter is added.

## Acceptance criteria

The implementation is acceptable when:

* Passive/offline mode is idempotent after token collection.
* It performs no login unless `allow_login_submission=true`.
* It performs no large dictionary attack unless `allow_large_dictionary_attack=true` and a separate plan authorizes it.
* It performs no forged-token submission unless `allow_forged_token_submission=true`.
* It handles missing tokens, malformed JWTs, unsupported algorithms, invalid base64url, timeouts, and connection errors gracefully.
* It enforces the candidate budget.
* It redacts tokens and secret candidates consistently in logs, evidence excerpts, and findings.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `candidate`, `rejected`, and `stale` statuses correctly.
* It defines only `WeakSigningKeySignature` and `WeakSigningKeyFinding` as stub-specific types.
* Unit tests cover JWT parsing, HMAC signing input reconstruction, HS256/HS384/HS512 verification, dictionary budget enforcement, constant-time comparison use, raw-secret redaction, active-proof gating, unsupported algorithms, malformed tokens, and negative assertions.
* Fixture tests cover weak HS256, strong HS256, weak HS384, weak HS512, RS256 out-of-scope behavior, malformed token handling, and optional forged-token proof.
* AI is not called.
