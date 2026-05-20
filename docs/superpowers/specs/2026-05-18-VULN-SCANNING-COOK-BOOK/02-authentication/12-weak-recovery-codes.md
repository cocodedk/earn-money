---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 12
slug: weak-recovery-codes
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.12 Weak recovery codes

> Phase 2 — Authentication · Category: MFA

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

Detect recovery codes that are short, predictable, duplicated, reused, or generated from a small search space. Recovery codes bypass the normal MFA factor, so weak codes can turn MFA into a thin second password. The runner cares because this check finds risky fallback authentication paths without guessing codes, brute forcing, or testing real users.

## Inputs

The runner receives a shared `ScanTarget` plus optional authenticated test context.

Required:

* `target`: shared `ScanTarget`.
* `base_url`: normalized from `target`.
* `evidence_store`: shared evidence persistence interface.
* `http_client`: scanner HTTP client with redirect, timeout, TLS, and cookie-jar handling.
* `run_id`: stable scan run identifier.

Optional:

* `credentials`: username/password or session bootstrap for a disposable test account.
* `mfa_test_account`: boolean. Must be `true` before the runner performs MFA enrollment, recovery-code generation, regeneration, or login-flow verification.
* `active_auth_allowed`: boolean. Default `false`.
* `recovery_code_paths`: small configured list of candidate paths, used only after authenticated navigation or fixture metadata suggests MFA features exist.
* `max_pages`: default `20`.
* `max_regenerations`: default `0`, maximum `1`.
* `verify_single_use`: default `false`. Only allowed in fixture or disposable-account mode.
* `min_single_code_entropy_bits`: default `40`.
* `min_code_length`: default `10` for numeric-only codes, `8` for mixed alphanumeric codes.
* `request_timeout_ms`: default from shared scanner config.
* `max_runtime_ms`: default from shared phase budget.

The runner must not require credentials for a safe no-op result. If credentials are absent, it may still inspect public pages for MFA recovery-code documentation, but it must not report a confirmed weak recovery-code finding from documentation alone.

## Detection logic

### Scope

This stub checks recovery-code generation and handling only. It does not brute force MFA, bypass MFA, test leaked codes, or try credentials against real accounts.

In scope:

* Recovery or backup codes shown during MFA setup.
* Recovery or backup codes shown on an authenticated MFA settings page.
* Recovery-code regeneration responses.
* Duplicate codes within the same generated set.
* Low search-space codes based on observed format.
* Sequential or timestamp-like codes.
* Optional one-time-use verification with a disposable fixture account.

Out of scope:

* Guessing recovery codes.
* Password spraying.
* Login brute force.
* Testing against real users.
* Social recovery flows.
* Support-desk bypass.
* Email reset flows.

### Discovery

Use response evidence, not hostname assumptions.

The runner may discover candidate MFA and recovery-code pages through:

1. Authenticated navigation links and forms.
2. Buttons or labels containing terms such as:

   * `mfa`
   * `2fa`
   * `two-factor`
   * `two factor`
   * `authenticator`
   * `backup codes`
   * `recovery codes`
   * `regenerate codes`
   * `download codes`
3. JSON route metadata or API responses that mention recovery-code operations.
4. Explicit fixture metadata.
5. Configured `recovery_code_paths`, but only as candidate probes. Do not infer technology or vulnerability from path names alone.

Allowed safe methods for discovery:

* `GET`
* `HEAD`
* authenticated `GET` using the disposable test account session

Blocked during discovery:

* `POST`
* `PUT`
* `PATCH`
* `DELETE`
* clicking destructive controls
* submitting MFA challenges
* generating new recovery codes unless active fixture mode is enabled

### Code extraction

Only inspect recovery codes that the application displays to the authenticated disposable account.

A candidate recovery-code set is detected when a response contains:

* a page, JSON body, or download response labeled as recovery or backup codes, and
* two or more code-like tokens near that label, or
* a structured field such as `recoveryCodes`, `backupCodes`, `codes`, or equivalent, and
* no evidence that the values are placeholders or documentation examples.

Do not persist raw recovery codes. Extract only derived properties:

* count
* code lengths
* character classes
* duplicate count
* sortedness indicators
* sequential-pattern indicator
* timestamp-like indicator
* per-code salted hash
* response evidence ID
* source URL
* source content type
* redaction status

Use a scan-run salt for hashes. Do not log the salt.

### Entropy estimate

Estimate the search space from the observed character set and length.

Character set sizes:

* numeric: `10`
* lowercase alpha: `26`
* uppercase alpha: `26`
* mixed alpha: `52`
* hexadecimal: `16`
* base32-like: `32`
* base36-like: `36`
* alphanumeric mixed: `62`
* unknown printable token: conservative observed alphabet size, minimum `10`

For a uniform-looking code:

```text
estimated_bits = log2(character_set_size ^ length)
```

For separated code groups, remove separators before calculating length. Examples:

* `123456` has length `6`, numeric charset, about `19.9` bits.
* `1234-5678` has length `8`, numeric charset, about `26.6` bits.
* `A7K9-P2QM` has length `8`, alphanumeric-like charset, about `47.6` bits.

Use the weakest observed code as the single-code estimate.

### Weakness rules

Create a `WeakRecoveryCodesSignature` when one or more deterministic rules match.

Confirmed finding rules:

* duplicate codes exist in the same generated set
* codes are sequential, such as `000001`, `000002`, `000003`
* codes are timestamp-like and share the same timestamp prefix or suffix
* a regenerated set repeats one or more old code hashes
* optional disposable-account verification proves a recovery code can be used more than once

Candidate finding rules:

* numeric-only code length is below `min_code_length`
* estimated single-code entropy is below `min_single_code_entropy_bits`
* all codes share a long common prefix or suffix not explained by formatting
* code set appears sorted and adjacent with small numeric deltas
* code values appear derived from user-visible account data, but only if the value is already visible in the same test account context

Rejected rules:

* only documentation examples are found
* only placeholder text is found, such as `XXXX-XXXX`
* no authenticated recovery-code page is found
* MFA is not configured on the disposable account and active enrollment is not allowed
* raw codes cannot be observed safely
* the scanner would need to guess, brute force, or test real users

### Confidence

Use deterministic evidence only.

`high`:

* duplicate, sequential, timestamp-like, repeated-after-regeneration, or reusable-code evidence is present
* evidence comes from the authenticated disposable account or fixture
* raw code values were redacted before persistence

`medium`:

* observed code format has low estimated entropy
* the scanner saw a real generated code set
* no brute force or verification was performed

`low`:

* only partial evidence is available
* labels strongly suggest recovery codes, but the scanner cannot safely inspect generated values
* public documentation suggests weak examples, but no live generated code was observed

### Finding status

* `confirmed`: at least one confirmed rule matched.
* `candidate`: at least one candidate rule matched and no confirmed rule matched.
* `rejected`: the check ran and did not find usable evidence or found only safe formats.
* `stale`: previously stored evidence no longer matches current responses, the account state changed, or the evidence cannot be reproduced within scan budget.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only stub-specific types.

```ts
export type WeakRecoveryCodesSignature = {
  signature_id: string;
  source:
    | "mfa_settings_page"
    | "mfa_enrollment_page"
    | "recovery_code_api"
    | "recovery_code_download"
    | "regeneration_response"
    | "fixture_probe";

  evidence_ids: string[];

  code_count: number | null;
  observed_lengths: number[];
  observed_character_classes: Array<
    | "numeric"
    | "lower_alpha"
    | "upper_alpha"
    | "mixed_alpha"
    | "hex"
    | "base32_like"
    | "base36_like"
    | "alphanumeric_mixed"
    | "unknown_printable"
  >;

  estimated_single_code_entropy_bits: number | null;
  estimated_set_entropy_bits: number | null;

  duplicate_count: number;
  sequential_pattern: boolean;
  timestamp_like_pattern: boolean;
  common_prefix_length: number;
  common_suffix_length: number;

  regeneration_compared: boolean;
  repeated_after_regeneration: boolean | null;

  single_use_verified: boolean;
  reusable_code_verified: boolean | null;

  matched_rules: string[];
  redaction_status: "raw_not_stored" | "redacted" | "hash_only" | "unknown";
};
```

```ts
export type WeakRecoveryCodesFinding = {
  finding_id: string;
  target: ScanTarget;

  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  severity: "low" | "medium" | "high";

  title: "Weak recovery codes";
  category: "Authentication";
  subcategory: "MFA";
  phase: 2;
  spec: 12;
  slug: "weak-recovery-codes";

  signatures: WeakRecoveryCodesSignature[];
  evidence: Evidence[];

  affected_urls: string[];
  account_context:
    | "none"
    | "public_only"
    | "authenticated_disposable"
    | "fixture_disposable";

  mutation_performed: boolean;
  mutation_types: Array<
    | "mfa_enrollment"
    | "recovery_code_generation"
    | "recovery_code_regeneration"
    | "single_use_verification"
  >;

  summary: string;
  remediation: string;

  created_at: string;
  updated_at: string;
};
```

Evidence records must store redacted bodies only. If the response contains real recovery codes, replace each code with a stable placeholder before persistence:

```text
RECOVERY_CODE_REDACTED[index=1,length=8,charset=numeric,hash=scan-local-sha256:...]
```

Do not persist:

* raw recovery codes
* full cookies
* session tokens
* passwords
* MFA seeds
* QR-code secrets
* TOTP secrets
* user PII beyond the disposable account identifier already used by the scan

## Safety

Default behavior is read-only.

Allowed without active auth:

* public `GET` and `HEAD`
* authenticated `GET` when the session is already provided
* parsing labels, forms, and redacted code properties
* rejected or low-confidence reporting when the runner cannot safely inspect codes

Allowed only when all are true:

* `active_auth_allowed=true`
* `mfa_test_account=true`
* the account is marked disposable in config or fixture metadata
* the action is inside `target` scope
* the action is needed for this check

Then the runner may perform at most:

* one MFA setup flow if the fixture requires it
* one recovery-code generation
* one recovery-code regeneration when `max_regenerations=1`
* one single-use verification when `verify_single_use=true`

Blocked always:

* brute forcing recovery codes
* generating code guesses
* using leaked or user-supplied recovery-code lists
* testing against real user accounts
* retrying many code variants
* using recovery codes from one account against another account
* continuing after lockout, captcha, fraud warning, or rate-limit response
* storing raw recovery codes
* sending recovery codes to AI or external services

HTTP method discipline:

* Discovery uses `GET` and `HEAD`.
* State-changing methods require active disposable-account mode.
* The runner must classify forms and buttons before submitting them.
* The runner must not submit a form if its purpose is unclear.
* The runner must stop on unexpected confirmation pages unless fixture metadata explicitly allows the next step.

Payload restrictions:

* No password lists.
* No recovery-code wordlists.
* No randomized guessing.
* No more than one generated code value may be used for optional single-use verification.
* No code value may be retried more than once, and only in the same disposable account session.

PII handling:

* Treat recovery codes as secrets.
* Redact before evidence persistence.
* Do not include raw codes in logs, errors, findings, reports, or LLM prompts.
* Store only derived metrics and salted hashes.

AI involvement:

* `None`.

Deterministic gap:

* None. The check can be implemented with HTTP evidence, DOM parsing, JSON parsing, token classification, entropy estimates, and strict state-machine rules.

## Pass/fail check

### Positive assertions

A run against a weak fixture must:

* authenticate only with the configured disposable account
* detect the MFA or recovery-code area from response evidence
* extract derived properties from the generated recovery-code set
* redact all raw recovery codes before evidence persistence
* create one `WeakRecoveryCodesFinding`
* set `status="confirmed"` when duplicate, sequential, timestamp-like, repeated-after-regeneration, or reusable-code evidence is present
* set `status="candidate"` when only low entropy or short code format is observed
* set `confidence="high"` for duplicate, sequential, repeated-after-regeneration, or reusable evidence
* set `confidence="medium"` for low-entropy generated codes without reuse proof
* include at least one `WeakRecoveryCodesSignature`
* include evidence IDs for every matched rule
* include affected authenticated URL or route
* include clear remediation text
* complete within the configured phase budget

Example expected weak signals:

* `123456`, `123457`, `123458`
* ten numeric six-digit recovery codes
* duplicated recovery codes in one set
* regenerated codes that repeat prior code hashes
* a recovery code that remains valid after successful use in a disposable fixture account

### Negative assertions

The runner must not:

* guess recovery codes
* brute force MFA
* use leaked code lists
* test against real user accounts
* submit recovery-code candidates without `verify_single_use=true`
* perform any state-changing request unless `active_auth_allowed=true` and `mfa_test_account=true`
* click a regenerate button unless `max_regenerations=1`
* persist raw recovery codes
* log raw recovery codes
* send raw recovery codes to AI
* infer expected behavior from hostname, framework, or fixture name
* report a confirmed finding from public documentation examples only
* treat placeholder codes as real generated codes
* continue after lockout, captcha, fraud warning, or rate-limit response
* retry state-changing requests after timeout unless the operation is known idempotent
* downgrade a previous confirmed finding to rejected without marking the old evidence stale

### Rejection assertions

A safe target with strong recovery codes must produce either:

* no finding, or
* a `WeakRecoveryCodesFinding` with `status="rejected"` and evidence explaining why no weak pattern matched

A run without credentials must:

* perform no authenticated or state-changing requests
* return `rejected` or no finding
* record that authenticated recovery-code inspection was not possible

A run where recovery codes are not visible must:

* not attempt bypasses
* not attempt guesses
* return `rejected` or `candidate` only if safe response evidence supports it

## Test fixtures

Use a new fixture slug:

```text
weak-recovery-codes
```

The fixture should expose a small authenticated demo app with a disposable account and MFA settings.

Required fixture behavior:

* Login with configured disposable credentials.
* MFA settings page has a recovery-code section.
* The weak mode generates ten six-digit numeric recovery codes.
* At least one test variant generates sequential codes.
* At least one test variant generates duplicate codes.
* At least one test variant repeats codes after regeneration.
* Optional variant allows a recovery code to be used twice for single-use verification.
* Strong mode generates mixed alphanumeric recovery codes above the configured entropy threshold.
* Documentation page includes placeholder/example recovery codes that must not be treated as real generated codes.

Suggested routes:

```text
GET  /login
POST /login
GET  /account/security
GET  /account/security/mfa
POST /account/security/mfa/enable
GET  /account/security/mfa/recovery-codes
POST /account/security/mfa/recovery-codes/regenerate
POST /login/mfa/recovery
```

The runner must not hard-code these routes as universal application behavior. They are fixture routes only. Production detection must come from navigation evidence, form evidence, API evidence, or explicit config.

Fixture modes:

```text
WEAK_RECOVERY_CODES_MODE=short_numeric
WEAK_RECOVERY_CODES_MODE=sequential
WEAK_RECOVERY_CODES_MODE=duplicate
WEAK_RECOVERY_CODES_MODE=repeated_after_regeneration
WEAK_RECOVERY_CODES_MODE=reusable
WEAK_RECOVERY_CODES_MODE=strong
WEAK_RECOVERY_CODES_MODE=documentation_only
```

If reusing an existing training fixture is preferred, use only an intentionally vulnerable local fixture. Do not point this spec at a public target or a shared test account.

## Acceptance criteria

Implementation is acceptable when:

* The runner is idempotent in read-only mode.
* State-changing behavior is disabled by default.
* State-changing behavior requires a disposable test account and explicit active-auth config.
* The runner never guesses or brute forces recovery codes.
* The runner never tests real user accounts.
* The runner extracts code properties without persisting raw codes.
* The runner redacts raw codes before evidence storage.
* The runner estimates entropy deterministically from observed format.
* The runner detects duplicate, sequential, timestamp-like, repeated, and short-code patterns.
* The runner separates `candidate`, `confirmed`, `rejected`, and `stale` states.
* The runner uses only `low`, `medium`, and `high` confidence.
* The runner uses shared `ScanTarget` and `Evidence`.
* The runner defines only `WeakRecoveryCodesSignature` and `WeakRecoveryCodesFinding`.
* The runner handles missing credentials without error.
* The runner handles TLS errors, redirects, 401, 403, 404, 429, and 5xx responses gracefully.
* The runner stops safely on captcha, lockout, fraud warning, or rate-limit responses.
* The runner uses bounded requests and no flaky retries.
* The runner completes within the configured phase budget.
* Tests assert that raw recovery codes do not appear in logs, evidence, findings, reports, snapshots, or exceptions.
* Tests assert that no `POST`, `PUT`, `PATCH`, or `DELETE` is sent in read-only mode.
* Tests assert that public documentation examples do not create confirmed findings.
* Tests assert that strong generated recovery codes produce no weak finding or a rejected finding.
* Tests assert that weak fixture modes produce the expected candidate or confirmed finding.

