---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 19
slug: duplicate-account-confusion
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.19 Duplicate account confusion

> Phase 2 — Authentication · Category: Registration

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

Detect registration flows that allow two accounts to represent the same human identity after normalization, such as email case folding, whitespace trimming, Unicode normalization, or configured alias rules. A runner cares because these bugs can break password reset, account recovery, notifications, audit trails, and ownership checks.

## Inputs

The runner receives a shared `ScanTarget` and uses shared `Evidence` records for all captured requests and responses.

Required input:

* `target.url`: base URL in scope.

Optional input:

* `credentials`: not required by default. Existing authenticated context may be used only for discovery, not for creating duplicate accounts.
* `registration_paths`: explicit registration endpoints to test. Example: `/register`, `/signup`, `/api/register`.
* `login_paths`: optional login endpoints used to confirm independent access for synthetic accounts.
* `password_reset_paths`: optional reset endpoints used only in fixtures or when explicitly allowed.
* `allow_mutating_registration`: default `false`. The runner must not create accounts unless this is `true`.
* `synthetic_email_domain`: required when mutating tests are enabled. Must be a controlled test domain or local mail sink domain.
* `synthetic_account_prefix`: default `vsdup`.
* `max_registration_attempts`: default `3`, hard maximum `6`.
* `request_timeout_ms`: default from shared runner settings.
* `follow_redirects`: default `true`, bounded by shared redirect limits.
* `identifier_variants`: optional list of enabled variant rules:

  * `email_case_fold`
  * `username_case_fold`
  * `ascii_trim`
  * `unicode_nfc_nfd`
  * `provider_alias_configured`
  * `custom`
* `verify_login_after_registration`: default `true` when login endpoint is known.
* `use_mail_sink`: default `false`. Required for email verification or password reset checks.
* `store_raw_identifiers`: default `false`. Store hashes and redacted values unless the shared evidence store explicitly permits sensitive test data.

## Detection logic

### 1. Discovery

The runner first performs read-only discovery.

Allowed discovery actions:

* `GET` the target URL and in-scope login or registration pages.
* Parse HTML forms for registration-like actions.
* Parse links with labels or paths containing `register`, `signup`, `sign-up`, `create-account`, or `join`.
* Detect JSON registration endpoints only from observed forms, scripts, documented API links, or configured paths.
* Record method, action URL, content type, field names, CSRF fields, and response status as `Evidence`.

The runner must not infer expected behavior from the hostname, framework, favicon, server header, or product name.

If no registration endpoint is found and none is configured, return no finding with status `rejected` and confidence `high`.

### 2. Mutating gate

Account creation is not read-only.

The runner may submit registration forms only when all of these are true:

* `allow_mutating_registration=true`.
* The registration endpoint is in scope.
* A controlled synthetic identifier domain is configured.
* The endpoint has enough fields to build a valid synthetic account.
* The request count stays inside `max_registration_attempts`.

If any condition is missing, the runner records discovery evidence and exits without a vulnerability finding.

### 3. Baseline account creation

Create one synthetic account with a unique nonce.

Example identifiers:

* Email: `vsdup-<nonce>@<synthetic_email_domain>`
* Username: `vsdup_<nonce>`

The runner must generate a strong password for the synthetic account but must not persist the raw password outside volatile test state.

Record:

* registration request metadata,
* response status,
* redirect target,
* stable response body markers,
* created account indicator if present,
* verification requirement if present.

Do not store cookies, bearer tokens, CSRF tokens, or raw passwords in finding details. Use redacted evidence.

If baseline creation fails because the form rejects synthetic input, return status `rejected` with confidence `medium`.

### 4. Variant account attempts

Build variants from enabled rules only.

Default safe variants:

* Email case fold:

  * `vsdup-<nonce>@example.test`
  * `VSDUP-<nonce>@example.test`
* Username case fold:

  * `vsdup_<nonce>`
  * `VSDUP_<nonce>`

Conditionally enabled variants:

* ASCII trim:

  * leading or trailing spaces only when the form accepts them and the value is safely encoded.
* Unicode normalization:

  * NFC and NFD forms of the same configured local part or username.
* Provider alias:

  * plus-addressing or dot-folding only when explicitly configured for the controlled mail sink. Do not assume Gmail, Microsoft, Apple, or any real provider behavior.
* Custom:

  * caller-provided variant pairs for the fixture or target.

For each variant, submit a second registration attempt using the same non-sensitive fields and a separate synthetic password.

### 5. Classification signals

A secure application usually does one of these:

* rejects the second registration as an existing account,
* returns a generic duplicate-account response,
* requires a verified ownership flow before linking,
* treats the values as distinct everywhere and does not normalize them into the same identity later.

A candidate finding exists when the runner observes one or more of these deterministic signals:

* The second registration is accepted even though the application later displays both accounts with the same normalized identifier.
* The second registration is accepted, and login or profile evidence shows both accounts share the same canonical email or username.
* One flow treats the identifiers as the same, while another flow treats them as separate.
* Password reset, email verification, or account lookup becomes ambiguous for the synthetic identifiers.
* The application creates two separate user IDs for identifiers that its own UI, API, or recovery flow treats as equivalent.

A confirmed finding requires stronger proof:

* Account A and Account B are both independently created, and
* both can be authenticated or observed as separate account records, and
* at least one application-owned flow treats their identifier as the same normalized identity.

If only registration acceptance is observed without a collision signal, mark the result `candidate` with confidence `low` or `medium`, not `confirmed`.

### 6. Evidence comparison

Use deterministic comparison only.

Compare:

* HTTP status codes,
* redirect chains,
* registration success markers,
* duplicate-account error markers,
* authenticated profile fields,
* stable user IDs or redacted user references,
* mail sink messages for synthetic recipients,
* password reset responses from fixture-safe paths,
* normalized identifiers returned by the application.

Do not compare raw session cookies. Do not store raw account passwords. Do not rely on timing as the only signal.

### 7. Confidence

Use `high` when:

* two synthetic accounts are created,
* both have separate app-owned account references,
* the app returns the same normalized identifier or ambiguous recovery behavior.

Use `medium` when:

* the duplicate registration appears accepted,
* a collision signal exists,
* but login or account reference confirmation is incomplete.

Use `low` when:

* only registration text suggests success,
* the app hides whether an account was created,
* or the runner cannot complete login verification.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only these stub-specific types:

```typescript
type DuplicateAccountConfusionVariantRule =
  | "email_case_fold"
  | "username_case_fold"
  | "ascii_trim"
  | "unicode_nfc_nfd"
  | "provider_alias_configured"
  | "custom";

type DuplicateAccountConfusionCollisionSignal =
  | "duplicate_registration_accepted"
  | "same_normalized_identifier_returned"
  | "separate_accounts_same_display_identifier"
  | "login_ambiguous"
  | "password_reset_ambiguous"
  | "email_verification_ambiguous"
  | "lookup_flow_conflict";

type DuplicateAccountConfusionSignature = {
  registration_endpoint: string;
  registration_method: "GET" | "POST" | "PUT" | "PATCH" | "unknown";
  identifier_kind: "email" | "username" | "phone" | "external_subject" | "unknown";
  variant_rule: DuplicateAccountConfusionVariantRule;
  primary_identifier_hash: string;
  variant_identifier_hash: string;
  normalized_identifier_hash?: string;
  collision_signals: DuplicateAccountConfusionCollisionSignal[];
  account_a_ref_hash?: string;
  account_b_ref_hash?: string;
  evidence_ids: string[];
  confidence: "low" | "medium" | "high";
};

type DuplicateAccountConfusionFinding = {
  target: ScanTarget;
  signature: DuplicateAccountConfusionSignature;
  evidence: Evidence[];
  status: "candidate" | "confirmed" | "rejected" | "stale";
  title: "Duplicate account confusion";
  summary: string;
  impact: string;
  remediation: string;
  detected_at: string;
};
```

Persistence rules:

* Store evidence IDs in the signature.
* Store hashes of synthetic identifiers, not raw values, unless shared evidence policy allows raw synthetic data.
* Store redacted request and response evidence.
* Never persist raw passwords, session cookies, bearer tokens, CSRF tokens, or mail sink credentials.
* Mark findings `stale` if a later run shows the duplicate path no longer accepts the variant.
* Deduplicate findings by target, registration endpoint, identifier kind, variant rule, and normalized identifier hash.

## Safety

This check has two modes.

Read-only mode:

* Performs endpoint discovery only.
* Does not submit registration forms.
* Does not create accounts.
* Does not request password reset.
* Does not produce a vulnerability finding unless prior evidence already exists in the scan context.

Mutating mode:

* Runs only when `allow_mutating_registration=true`.
* Creates only synthetic accounts with controlled identifiers.
* Uses a bounded number of attempts.
* Uses only in-scope endpoints.
* Does not touch real user accounts.
* Does not use leaked data, common usernames, employee names, customer names, or public email addresses.
* Does not brute force.
* Does not retry many variants.
* Does not attempt account takeover.
* Does not delete accounts unless the fixture exposes a documented safe cleanup endpoint and the shared runner allows cleanup.
* Does not send email to real external recipients. Verification and reset checks require a local or controlled mail sink.

HTTP method discipline:

* Discovery uses `GET` and `HEAD` where safe.
* Registration uses the method declared by the observed form or configured API endpoint.
* Password reset checks are disabled by default and allowed only for synthetic accounts in fixtures or explicitly authorized targets.
* No destructive methods are used.

Payload restrictions:

* Use unique synthetic values.
* Use minimal form fields.
* Do not upload files.
* Do not include scripts, XSS payloads, SQL payloads, or shell metacharacter payloads.
* Do not bypass CAPTCHA, MFA, email verification, bot checks, or rate limits.

PII handling:

* Treat identifiers as sensitive even when synthetic.
* Redact raw identifiers in logs by default.
* Hash account references before storing in signatures.
* Keep raw values only in volatile runner memory when needed for login confirmation.

AI involvement:

* `None`.

Deterministic gap:

* If the app gives only opaque success pages and no login, profile, mail sink, or account reference can be observed, the runner must not ask AI to infer whether a duplicate exists. It records a low-confidence candidate only if deterministic response evidence supports it.

## Pass/fail check

### Positive assertions

A test passes when the runner:

* Discovers a registration endpoint from configured paths or observed forms.
* Refuses mutating checks when `allow_mutating_registration=false`.
* Creates a baseline synthetic account only when mutating checks are allowed.
* Creates at most the configured number of variant accounts.
* Detects a duplicate-account confusion candidate when a variant registration is accepted and the app later exposes a collision signal.
* Marks the finding `confirmed` only when two separate synthetic accounts and one shared normalized identity signal are observed.
* Stores `DuplicateAccountConfusionSignature` with:

  * registration endpoint,
  * identifier kind,
  * variant rule,
  * collision signals,
  * evidence IDs,
  * confidence.
* Stores shared `Evidence` for each relevant request and response.
* Redacts raw passwords, cookies, tokens, and credentials.
* Sets confidence according to the observed proof level.

### Negative assertions

The runner must not:

* create accounts in read-only mode,
* test against real user accounts,
* use real customer, employee, or public email addresses,
* use leaked password lists,
* brute force registration, login, or password reset,
* retry many variants,
* assume Gmail-style plus or dot behavior unless configured,
* hard-code hostname or framework to expected behavior,
* classify two unrelated unique accounts as a duplicate-account bug,
* mark a finding `confirmed` based only on a 200 response,
* treat a generic “check your email” message as proof of account creation,
* submit password reset requests unless the account is synthetic and the mail sink or fixture is configured,
* persist raw passwords, session cookies, bearer tokens, CSRF tokens, or mail sink credentials,
* exceed `max_registration_attempts`,
* follow out-of-scope redirects for mutation,
* bypass CAPTCHA, MFA, verification, or rate limits.

### Rejection cases

Return status `rejected` with evidence when:

* no registration endpoint is found,
* mutating checks are disabled,
* the baseline synthetic account cannot be created,
* the variant registration is rejected as a duplicate,
* no collision signal is observed,
* the app treats the identifiers as distinct in all observed flows.

## Test fixtures

Use a purpose-built fixture: `duplicate-account-confusion`.

The fixture should expose:

* `GET /register`: HTML registration form with CSRF token.
* `POST /register`: creates accounts.
* `POST /login`: authenticates synthetic accounts.
* `GET /me`: returns account reference and displayed identifier.
* Optional `POST /password-reset`: writes reset messages to a local mail sink only.

Buggy fixture behavior:

* Registration uniqueness checks raw email exactly.
* Profile display lowercases and trims email.
* Password reset or lookup lowercases and trims email.
* The app accepts both:

  * `vsdup-<nonce>@mail.test`
  * `VSDUP-<nonce>@mail.test`
* Both accounts receive separate internal user IDs.
* `/me` returns the same displayed normalized email for both accounts.

Expected scanner result:

* one `confirmed` finding,
* `variant_rule="email_case_fold"`,
* collision signals include:

  * `duplicate_registration_accepted`,
  * `same_normalized_identifier_returned`,
  * `separate_accounts_same_display_identifier`,
* confidence `high`.

Negative fixture behavior:

* A fixed variant of the fixture rejects the second registration with a duplicate-account response.
* Expected scanner result is `rejected` with confidence `high`.

Optional smoke fixture:

* Use `juice-shop` only as a negative or discovery smoke test if its registration behavior is stable in the local container.
* Do not rely on `juice-shop` for the positive case unless the fixture is pinned and known to expose this exact bug.

## Acceptance criteria

The implementation is acceptable when:

* It is idempotent across repeated runs by using a fresh nonce per run.
* It has no effect unless mutating registration tests are explicitly enabled.
* It completes within the shared scan budget and the configured registration attempt limit.
* It handles TLS, connection, timeout, redirect, and malformed HTML errors without crashing.
* It records useful evidence for discovery, baseline registration, variant registration, login confirmation, and collision comparison.
* It does not log or persist secrets.
* It does not create accounts outside scope.
* It does not send mail to external recipients.
* It does not depend on response timing alone.
* It uses deterministic checks only.
* It returns stable `candidate`, `confirmed`, `rejected`, or `stale` status.
* It keeps confidence limited to `low`, `medium`, or `high`.
* It uses shared `ScanTarget` and `Evidence`.
* It defines only `DuplicateAccountConfusionSignature` and `DuplicateAccountConfusionFinding` as stub-specific persistence types.
* It passes positive and negative fixture tests without flaky retries.

