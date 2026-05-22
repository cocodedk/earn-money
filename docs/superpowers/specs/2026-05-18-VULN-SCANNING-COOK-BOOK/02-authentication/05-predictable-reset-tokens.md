---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 5
slug: predictable-reset-tokens
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.5 Predictable reset tokens

> Phase 2 — Authentication · Category: Password reset

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

Detect password reset flows that issue reset tokens with predictable structure, weak entropy, reuse, or direct derivation from stable user data. A runner cares because a predictable token can let an attacker reset another user’s password without owning that user’s email account.

## Inputs

The runner receives a shared `ScanTarget` and optional authentication material from the execution profile.

### Required

* `ScanTarget` from `../00-shared-schema.md`.
* Base URL in scope.
* HTTP client with redirect handling disabled by default, then enabled only where explicitly needed.
* Evidence collector that stores shared `Evidence`.

### Optional

* `known_account_email`: an email address for a scanner-controlled account.
* `known_account_password`: password for that account, if login is needed to discover account metadata.
* `second_known_account_email`: a second scanner-controlled account used to compare reset tokens across accounts.
* `reset_endpoint_hint`: configured path or URL for the password reset request endpoint.
* `mailbox_adapter`: test mailbox adapter for scanner-owned accounts. Without this, the scanner may only inspect reset request responses and cannot confirm token contents delivered out of band.
* `max_reset_requests`: default `2` per scanner-owned account.
* `request_timeout_ms`: default from shared runner settings.
* `token_capture_patterns`: optional extra regex patterns for fixture-specific reset links.

### Non-goals

* Do not test third-party accounts.
* Do not brute force reset tokens.
* Do not change a password unless the fixture explicitly requires it and the target account is scanner-owned.
* Do not infer technology from hostnames, ports, banners, or fixture names alone.

## Detection logic

Detection is deterministic and based on reset request behavior, token capture, token parsing, and bounded comparison across scanner-owned accounts.

### 1. Discover reset flow

Use this order:

1. If `reset_endpoint_hint` is present, request it first.
2. Otherwise request the target root page and common unauthenticated pages found through same-origin links.
3. Search HTML forms and links for reset indicators:

   * link text or path containing `forgot`, `reset`, `password-reset`, `recover`, `recovery`
   * form inputs named like `email`, `username`, `user`, `login`
   * buttons or labels containing `forgot password`, `reset password`, `recover account`
4. Record all candidate endpoints as `PredictableResetTokenSignature`.

Only submit a reset request when the endpoint is same-origin and the form accepts a scanner-owned identifier.

### 2. Request reset for scanner-owned account

For each selected account, submit at most `max_reset_requests` reset requests.

Allowed methods:

* Use the form method from the page when present.
* If no form is present and the endpoint hint is configured, use `POST`.
* Do not use destructive verbs.

Allowed content types:

* `application/x-www-form-urlencoded`
* `multipart/form-data` only if the target form uses it
* `application/json` only if the endpoint clearly expects JSON from observed evidence

Record:

* request method
* normalized endpoint path
* status code
* redirect location, if present
* response headers relevant to reset behavior
* response body snippets after redaction
* captured reset links or tokens from the response or mailbox adapter

### 3. Capture token

Token sources, in priority order:

1. Reset link in scanner-owned mailbox.
2. Reset link in HTTP response body.
3. Reset token in redirect `Location`.
4. Reset token in JSON response.

Extract token values from common parameters and paths:

* query parameters: `token`, `resetToken`, `code`, `key`, `nonce`
* path fragments like `/reset/<token>`, `/password-reset/<token>`, `/recover/<token>`
* JSON fields with equivalent names

Do not log full reset links when they contain email addresses or other account identifiers. Store redacted links in `Evidence` and store token analysis separately.

### 4. Analyze token predictability

Run deterministic checks on captured tokens.

A token is suspicious when one or more checks match:

| Check                    | Condition                                                                                                                                    | Confidence |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| Static reuse             | Two reset requests for the same scanner-owned account return the same active token                                                           | high       |
| Cross-account reuse      | Two different scanner-owned accounts receive the same token                                                                                  | high       |
| Sequential integer       | Token is an integer and second token is adjacent or near-adjacent within the bounded sample                                                  | medium     |
| Timestamp-like           | Token fully or mostly matches current Unix time, milliseconds, ISO timestamp, or sortable date string                                        | medium     |
| Encoded stable data      | Base64/base64url/hex decoding contains the scanner-owned email, username, numeric user ID, or reset endpoint path without a MAC or signature | high       |
| Low entropy              | Token length and alphabet imply less than 64 bits of search space                                                                            | medium     |
| Trivial format           | Token is shorter than 16 characters and uses only decimal digits or lowercase hex                                                            | medium     |
| JWT without integrity    | Token parses as JWT with `alg: none`, missing signature, or stable predictable claims only                                                   | high       |
| Unsigned structured blob | Token decodes to JSON or key-value data with no detectable signature/MAC segment                                                             | high       |

A token is not suspicious only because it is readable. Signed JWTs and signed opaque framework tokens may be acceptable if they include a valid-looking signature segment and no deterministic weakness is observed in the bounded sample.

### 5. Confirm reset token acceptance safely

If the reset link can be opened without changing the password:

1. Request the reset link with `GET`.
2. Do not submit a new password.
3. Confirm only that the token is accepted by observing a reset form, `200` response, or explicit valid-token message.
4. If the token is rejected, mark the finding as `stale` or `rejected` depending on evidence.

Do not attempt token guessing. Do not mutate the account password unless the fixture contract explicitly permits it.

### 6. Status and confidence mapping

* `confirmed`: deterministic weakness is observed and the token is accepted or clearly issued by the target.
* `candidate`: suspicious token structure is observed, but token acceptance was not checked.
* `rejected`: candidate was disproved by later evidence.
* `stale`: token was previously observed but no longer accepted during validation.

Confidence values:

* `high`: token reuse, cross-account reuse, encoded stable account data without signature, unsigned JWT, or accepted deterministic token.
* `medium`: short token, timestamp-like token, sequential token, or low entropy from bounded samples.
* `low`: weak signal from reset endpoint behavior without captured token.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

### Stub-specific types

```ts
export type PredictableResetTokenConfidence = "low" | "medium" | "high";
export type PredictableResetTokenStatus =
  | "candidate"
  | "confirmed"
  | "rejected"
  | "stale";

export interface PredictableResetTokenSignature {
  endpoint_url: string;
  endpoint_path: string;
  method: "GET" | "POST";
  content_type?: string;
  identifier_field?: string;
  discovery_source:
    | "configured_hint"
    | "html_form"
    | "html_link"
    | "redirect"
    | "mailbox_link";
  observed_indicators: string[];
  evidence_ids: string[];
}

export interface PredictableResetTokenFinding {
  target: ScanTarget;
  signature: PredictableResetTokenSignature;
  status: PredictableResetTokenStatus;
  confidence: PredictableResetTokenConfidence;
  title: string;
  summary: string;
  token_source:
    | "mailbox"
    | "http_response"
    | "redirect_location"
    | "json_body"
    | "unknown";
  token_parameter?: string;
  token_fingerprint: string;
  token_format:
    | "opaque"
    | "integer"
    | "timestamp"
    | "hex"
    | "base64"
    | "base64url"
    | "jwt"
    | "json"
    | "unknown";
  observed_weaknesses: Array<
    | "static_reuse"
    | "cross_account_reuse"
    | "sequential_integer"
    | "timestamp_like"
    | "encoded_stable_data"
    | "low_entropy"
    | "trivial_format"
    | "jwt_without_integrity"
    | "unsigned_structured_blob"
  >;
  sample_count: number;
  affected_scanner_accounts: string[];
  evidence_ids: string[];
  remediation: string;
}
```

### Evidence handling

Persist evidence for:

* reset endpoint discovery
* reset request submission
* token delivery or capture
* redacted token analysis
* optional token acceptance check

Token storage rules:

* Never store full live reset tokens in plain text.
* Store a stable fingerprint, such as SHA-256 of the token plus runner salt.
* Store redacted token samples, preserving only length, alphabet class, and first/last two characters when needed.
* Redact email addresses and account identifiers from URLs and bodies.

## Safety

This stub is mostly read-only during discovery but can trigger password reset emails for scanner-owned accounts. Treat reset submission as a bounded, authorized mutation.

### HTTP-method discipline

Allowed:

* `GET` for discovery and safe reset-link validation.
* `POST` for reset requests to scanner-owned identifiers.
* `HEAD` only for endpoint existence checks if the runner supports it.

Forbidden:

* No `PUT`, `PATCH`, or `DELETE`.
* No password change submission unless explicitly enabled by fixture configuration.
* No token guessing, fuzzing, brute forcing, or wordlist use.
* No testing against accounts not supplied as scanner-owned inputs.

### Payload restrictions

* Submit only scanner-owned email addresses or usernames.
* Do not inject payloads into the reset form.
* Do not alter hidden fields except to replay the form’s provided CSRF token or required state value.
* Maximum reset submissions are bounded by `max_reset_requests`.

### PII handling

* Redact email addresses in logs and evidence.
* Store reset tokens only as fingerprints and redacted metadata.
* Do not persist mailbox contents beyond the reset message evidence needed for this check.

### AI involvement

AI: `None`.

Deterministic gap: none. The runner must not use an LLM to classify token weakness, infer application behavior, generate payloads, or decide whether an account is in scope.

## Pass/fail check

The implementation passes when all assertions below hold.

### Positive assertions

* Given a reset endpoint hint and a scanner-owned email, the runner submits a bounded reset request and records evidence.
* Given a reset token in a scanner-owned mailbox, the runner extracts the token and records a redacted token fingerprint.
* Given two identical tokens from separate reset requests for the same scanner-owned account, the runner creates a `confirmed` finding with `static_reuse` and `high` confidence.
* Given the same token issued to two different scanner-owned accounts, the runner creates a `confirmed` finding with `cross_account_reuse` and `high` confidence.
* Given a token that decodes to the scanner-owned email without a signature or MAC, the runner creates a finding with `encoded_stable_data` and `high` confidence.
* Given a short numeric, timestamp-like, or low-entropy token, the runner creates a `candidate` finding with `medium` confidence unless acceptance is also confirmed.
* Given an expired token that was previously captured but is rejected during validation, the runner marks the finding `stale`.

### Negative assertions

* The runner must not submit reset requests for emails, usernames, or account IDs not supplied as scanner-owned inputs.
* The runner must not brute force, mutate, or guess reset tokens.
* The runner must not change any password unless a fixture-specific test explicitly enables password mutation.
* The runner must not store full live reset tokens in evidence.
* The runner must not classify a signed JWT as vulnerable only because it is parseable.
* The runner must not assume expected behavior from hostname, fixture name, port, or product banner.
* The runner must not create a finding when no token is captured and no deterministic weakness is observed.
* The runner must not retry indefinitely on network failures, mailbox delays, or TLS errors.

## Test fixtures

Fixture remains `tbd` until the harness confirms which container exposes a predictable reset-token flow.

Preferred fixture contract:

* A local fixture with two scanner-owned accounts.
* A password reset endpoint reachable without prior authentication.
* A test mailbox or response-visible reset link.
* A deliberately weak reset token mode, such as:

  * static token per account
  * incremental numeric token
  * timestamp-derived token
  * base64-encoded email without signature
  * unsigned JWT or unsigned JSON blob

Candidate fixtures to verify:

| Fixture                                 | Use if                                                                                            | Expected weak behavior                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `webgoat`                               | The local lesson exposes reset-token or password-recovery token behavior with scanner-owned users | predictable or weak recovery token                |
| `juice-shop`                            | The local challenge exposes reset links or recovery material through a test mailbox/API           | weak reset or recovery flow                       |
| new slug, for example `reset-token-lab` | Existing fixtures do not expose deterministic token capture safely                                | purpose-built local endpoint with mailbox adapter |

The coding agent should prefer a purpose-built fixture over bending a real training app if the training app requires account takeover, guessing, or non-deterministic mailbox behavior.

## Acceptance criteria

* The scanner is idempotent for the same target and scanner-owned accounts.
* The scanner completes within the shared per-stub time budget.
* Reset requests are bounded and configurable.
* TLS errors, connection failures, missing mailbox adapter, and missing reset endpoint are handled as non-fatal rejected or no-finding outcomes.
* Evidence is enough to reproduce the decision without exposing full reset tokens.
* The finding schema uses only shared `ScanTarget`, shared `Evidence`, and the stub-specific types defined here.
* Results are deterministic across repeated runs against the same fixture state.
* No flaky retries: retry only once for transient network failure and once for mailbox polling if the mailbox adapter declares delayed delivery.
* The runner cleans up temporary mailbox state where the adapter supports cleanup.
* The implementation follows the coding-agent rules in `../00-shared-schema.md`.

