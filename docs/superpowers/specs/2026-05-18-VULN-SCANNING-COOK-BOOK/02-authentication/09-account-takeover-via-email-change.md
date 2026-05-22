---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 9
slug: account-takeover-via-email-change
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.9 Account takeover via email change

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

Detect account takeover paths where changing the email address on an authenticated account transfers control of the password reset channel without enough protection. The runner checks whether a scanner-owned account can change its email without reauthentication, whether the new email becomes active before verification, and whether password reset messages are routed to that new address before the change is confirmed.

This stub does not test real user accounts. It proves the weakness only with accounts and mailboxes created or explicitly provided for the scan.

## Inputs

The runner receives a shared `ScanTarget` and uses shared `Evidence` records for all HTTP requests, responses, page excerpts, and mailbox observations.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized from `target`.
* `auth_context`: authenticated session for a scanner-owned test account.
* `original_email`: email currently assigned to the scanner-owned account.
* `replacement_email`: unique scanner-controlled email address for this run.
* `mailbox_sink`: optional mailbox/catch-all/test mail API controlled by the scanner.
* `roe`: rule-of-engagement object or equivalent permission flag.

Optional config:

* `candidate_paths`: known profile/account paths to try first.
* `max_candidate_paths`: default `20`.
* `max_requests`: default `40`.
* `timeout_seconds`: default from shared runner settings.
* `allow_active_email_change`: default `false` unless explicitly enabled by RoE.
* `allow_password_reset_probe`: default `false` unless mailbox sink and RoE are present.
* `rollback_email_change`: default `true`.
* `require_recent_reauth_policy`: project policy flag. If true, missing reauthentication is a finding.
* `require_verified_email_before_reset_policy`: project policy flag. If true, reset-to-unverified-email is a finding.

Scanner-owned identity requirements:

* The account must be created for this scan or explicitly marked as a scanner test account.
* The replacement email must be unique per run.
* The replacement email must not belong to another user.
* The runner must not test email change against real customer, employee, admin, or production user accounts.

## Detection logic

The runner performs deterministic checks only. It does not infer expected behavior from hostname, framework, product name, or technology stack.

### 1. Discover candidate email-change surfaces

Use authenticated, low-volume crawling from the scanner-owned account.

Candidate sources:

* Links or forms containing profile, account, user, settings, email, security, or password text.
* HTML forms with fields named like `email`, `new_email`, `newEmail`, `current_email`, `currentEmail`, `password`, `current_password`, `currentPassword`.
* JSON/API responses that expose account settings links or email-change endpoints.
* OpenAPI or route metadata already collected by earlier discovery stubs.

Candidate endpoint examples:

* `GET /account`
* `GET /profile`
* `GET /settings`
* `GET /account/security`
* `POST /account/email`
* `PATCH /api/users/me`
* `PUT /api/account`
* `PATCH /api/account/email`

Record candidate evidence with:

* method
* path
* status code
* content type
* normalized form or JSON field names
* CSRF field presence
* visible labels or button text
* redacted snippets only

Do not submit mutations during discovery.

### 2. Establish baseline state

Using the authenticated scanner-owned account, read the current account email from one or more deterministic sources:

* profile page text
* account settings API response
* `/me` or current-user endpoint
* server-rendered form value

Store evidence for the observed `original_email`.

If the runner cannot observe the current email, it may still create a `candidate` finding from form structure, but it must not create a `confirmed` finding.

### 3. Check for high-risk email-change controls

Inspect candidate forms and API schemas for controls.

Signals that reduce risk:

* current password is required
* recent reauthentication challenge is required
* MFA challenge is required
* change is stored as pending until the new email is verified
* password reset continues to use the old verified email until verification
* old email receives a security notification
* session is invalidated after email change

Signals that increase risk:

* only `email` or `new_email` is required
* no current password field is present
* no recent reauth or MFA challenge appears before update
* API accepts the new email and returns updated user state immediately
* response marks the new email as verified or active
* password reset is routed to the new email before verification

This structural check may produce only `candidate` confidence unless active checks are allowed.

### 4. Perform controlled email-change check

Only run this step when all are true:

* `allow_active_email_change=true`
* RoE allows account mutation
* the authenticated account is scanner-owned
* `replacement_email` is scanner-controlled
* rollback is enabled or the fixture is disposable

Submit the smallest valid request needed to change the scanner-owned account email.

Rules:

* Preserve required CSRF tokens.
* Preserve normal browser/API headers needed for the app.
* Do not bypass UI constraints with brute force.
* Do not try many payload variants.
* Do not use another user's email.
* Do not use guessed account IDs.
* Do not use admin endpoints unless the authenticated account is an admin test fixture and RoE allows it.

After submission, classify the response:

* `reauth_required`: response redirects to login, asks for password, asks for MFA, or returns `401`, `403`, `409`, or equivalent challenge.
* `pending_verification`: response says verification is required and observed account state remains unchanged or marked pending.
* `changed_immediately`: observed profile/API state shows `replacement_email` as the account email without reauthentication and without completed verification.
* `unknown`: response is ambiguous and state cannot be read.

### 5. Verify whether the new email is active before verification

If state readback is available, check whether the replacement email appears as:

* primary login email
* verified email
* active recovery email
* password reset destination
* account identifier in `/me` or profile response

If the app stores both `email` and `pending_email`, treat it as safer when:

* `email` remains `original_email`
* `pending_email` is `replacement_email`
* reset/login flows still use `original_email` until verification

### 6. Optional password-reset routing check

Only run this step when all are true:

* `allow_password_reset_probe=true`
* mailbox sink is available
* account mutation already changed or pending-changed the scanner-owned account
* RoE allows password-reset email generation
* the runner will not consume reset tokens or change the password

Request a password reset for the scanner-owned account using the app's normal reset flow.

Accepted identifiers:

* original email
* replacement email
* username, if the app uses usernames and the profile exposes one to the account owner

The runner may check mailbox metadata and message headers/body snippets from the scanner-controlled sink.

The runner must redact reset links and tokens before persistence.

Confirmed weakness conditions:

* reset email is sent to `replacement_email` before the replacement email is verified; or
* reset flow accepts `replacement_email` as the account identifier before verification; or
* reset link references the scanner-owned account after only an unverified email change.

Do not click reset links. Do not submit a new password.

### 7. Roll back controlled mutation

If the runner changed the email, restore `original_email` using the same permitted account flow.

If rollback fails:

* keep the finding status no higher than `candidate` unless exploitability was already proven with safe evidence
* record `rollback_failed=true`
* mark the run for operator review
* do not continue with more mutation checks

### 8. Classification

Create signatures as follows:

`missing_reauthentication`

* Confirmed when the app changes the account email immediately from an authenticated session without requiring current password, MFA, or recent reauthentication, and policy requires reauth for email changes.
* Medium confidence if endpoint structure strongly shows no reauth but active mutation is not allowed.
* Rejected if current password, MFA, or recent login challenge is required.

`unverified_email_active_immediately`

* Confirmed when `replacement_email` becomes the active account email before verification.
* High confidence if profile/API readback proves it.
* Rejected if the email is stored only as pending.

`password_reset_routes_to_unverified_new_email`

* Confirmed when password-reset delivery or identifier acceptance uses `replacement_email` before verification.
* High confidence only when mailbox sink evidence proves delivery to `replacement_email`.
* Rejected if reset remains tied to `original_email` until verification.

`ambiguous_email_change_flow`

* Candidate only.
* Used when forms or responses suggest risk, but state cannot be safely changed or read.

## Persistence

Use the shared `ScanTarget` and `Evidence` types from `../00-shared-schema.md`. Do not redefine them here.

Define only stub-specific types:

```ts
export type EmailChangeAtoWeakness =
  | "missing_reauthentication"
  | "unverified_email_active_immediately"
  | "password_reset_routes_to_unverified_new_email"
  | "ambiguous_email_change_flow";

export type EmailChangeAtoControlState =
  | "missing"
  | "present"
  | "not_observed"
  | "not_applicable";

export interface EmailChangeAtoSignature {
  id: string;
  weakness: EmailChangeAtoWeakness;
  endpointMethod?: string;
  endpointPath?: string;
  observedOriginalEmailHash?: string;
  observedReplacementEmailHash?: string;
  currentPasswordRequired: EmailChangeAtoControlState;
  recentReauthRequired: EmailChangeAtoControlState;
  mfaRequired: EmailChangeAtoControlState;
  newEmailVerificationRequired: EmailChangeAtoControlState;
  oldEmailNotificationObserved: EmailChangeAtoControlState;
  passwordResetRoutedToReplacementEmail: EmailChangeAtoControlState;
  emailStateAfterChange:
    | "unchanged"
    | "pending_replacement"
    | "replacement_active"
    | "unknown";
  rollbackAttempted: boolean;
  rollbackSucceeded?: boolean;
  evidenceIds: string[];
}

export interface EmailChangeAtoFinding {
  id: string;
  targetId: string;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  severity: "low" | "medium" | "high" | "critical";
  signature: EmailChangeAtoSignature;
  evidenceIds: string[];
  summary: string;
  impact: string;
  remediation: string;
  mutationPerformed: boolean;
  rollbackRequired: boolean;
  rollbackSucceeded?: boolean;
  ai: null;
  createdAt: string;
  updatedAt: string;
}
```

Evidence requirements:

* Store full request/response metadata through shared `Evidence`.
* Redact cookies, CSRF tokens, password reset tokens, session IDs, authorization headers, and reset links.
* Hash emails before storing in signature fields unless the shared evidence store already handles PII protection.
* Keep enough evidence to prove state transition without storing mailbox secrets.
* Link all findings to evidence IDs, not raw response bodies.

Recommended evidence labels:

* `email_change_candidate_form`
* `email_change_baseline_state`
* `email_change_mutation_request`
* `email_change_mutation_response`
* `email_change_state_after`
* `email_change_reset_request`
* `email_change_mailbox_observation`
* `email_change_rollback_request`
* `email_change_rollback_result`

## Safety

Default behavior is passive discovery only. Active email-change checks require explicit RoE permission and scanner-owned accounts.

Hard safety rules:

* Do not test against real user accounts.
* Do not change another user's email address.
* Do not use guessed account IDs.
* Do not use leaked, harvested, or third-party emails.
* Do not consume password reset links.
* Do not change account passwords.
* Do not perform brute force.
* Do not retry many variants.
* Do not send reset emails to addresses not controlled by the scanner.
* Do not continue mutation checks after rollback failure.
* Do not classify a finding from technology name, framework, hostname, or guessed behavior.

HTTP method discipline:

* Use `GET` only during discovery and baseline reads.
* Use one normal state-changing request for email change when active checks are allowed.
* Use one normal state-changing request for rollback when needed.
* Use at most one password-reset request when allowed.
* Do not spray candidate endpoints with mutation requests.

PII handling:

* Treat emails as sensitive.
* Store hashes or redacted forms in signatures.
* Store raw emails only if the shared secure evidence layer already permits it.
* Redact mailbox message bodies except minimal snippets showing destination and template type.
* Always redact reset tokens and links.

AI involvement:

* `ai` is always `null`.
* No AI analysis is needed for detection, classification, or persistence.
* Any future AI summary must use validated findings only and must not read raw reset tokens or mailbox contents.

## Pass/fail check

### Confirmed finding assertions

A confirmed `missing_reauthentication` finding requires all of these:

* The account used is scanner-owned.
* Baseline evidence shows `original_email`.
* Mutation evidence shows an email-change request for `replacement_email`.
* The request succeeds without current password, MFA, or recent reauth challenge.
* Readback evidence shows `replacement_email` active, or the response returns updated account state.
* Evidence IDs are linked in the finding.
* Rollback was attempted if mutation occurred.

A confirmed `unverified_email_active_immediately` finding requires all of these:

* The replacement email was not verified by the runner.
* Readback evidence shows `replacement_email` active as the account email.
* The app does not keep the change only in a pending field.
* The finding includes before and after evidence.
* Rollback was attempted if mutation occurred.

A confirmed `password_reset_routes_to_unverified_new_email` finding requires all of these:

* The replacement email was not verified by the runner.
* Password reset was requested only for the scanner-owned account.
* Mailbox sink evidence shows reset delivery to `replacement_email`, or reset identifier acceptance proves the new email controls reset routing.
* Reset token and link are redacted.
* The runner did not click the reset link.
* The runner did not change the password.

### Candidate finding assertions

A candidate finding is allowed when:

* Form/API structure suggests email can be changed without sufficient controls, but active checks are disabled.
* The runner observes no current-password or reauth fields, but cannot safely mutate state.
* The response is ambiguous and readback is unavailable.
* The evidence supports the uncertainty.

Candidate findings must use `confidence: "low"` or `confidence: "medium"`.

### Rejected finding assertions

Create or update a rejected result when any of these are observed:

* Current password is required and enforced.
* MFA or recent reauth is required and enforced.
* Email change remains pending until verification.
* Password reset remains tied to the old verified email.
* Mutation request is denied with `401`, `403`, `409`, or equivalent challenge.
* The runner cannot prove the replacement email became active.
* The only signal is UI copy without state evidence.

### Negative assertions

The runner must not:

* mark a finding confirmed from UI text alone
* mark a finding confirmed when only a pending email is created
* mark a finding confirmed when reset delivery is not observed
* use a real user's account
* use a real user's email as `replacement_email`
* click password reset links
* change passwords
* brute force endpoints or field names
* bypass CSRF or authentication controls
* infer expected behavior from hostname or framework
* persist reset tokens, session cookies, or authorization headers
* continue after rollback failure except to record evidence and stop

## Test fixtures

Preferred fixture: new local fixture `email-change-ato`.

The fixture should expose one vulnerable app and several fixed variants so the runner can prove both positive and negative behavior.

### Vulnerable variant

Routes:

* `GET /login`
* `POST /login`
* `GET /account`
* `POST /account/email`
* `POST /forgot-password`
* test mailbox sink endpoint or in-memory mail capture

Behavior:

* authenticated user can change email by submitting only `new_email`
* no current password is required
* no recent reauth is required
* no verification is required
* account email updates immediately
* password reset sends to the new email immediately

Expected result:

* `missing_reauthentication`: confirmed
* `unverified_email_active_immediately`: confirmed
* `password_reset_routes_to_unverified_new_email`: confirmed when mailbox sink is enabled

### Fixed variant: current password required

Behavior:

* `POST /account/email` requires `current_password`
* missing or wrong password returns a challenge
* account email remains unchanged

Expected result:

* rejected
* no mutation remains

### Fixed variant: pending email verification

Behavior:

* `POST /account/email` stores `pending_email`
* `email` remains the original verified email
* reset flow continues to use the verified email
* new email becomes active only after a verification token is consumed

Expected result:

* rejected for active takeover
* optional informational evidence may note pending-email behavior

### Fixed variant: recent reauth required

Behavior:

* email-change request redirects to reauth or returns a reauth-required API response
* account email remains unchanged

Expected result:

* rejected

### Ambiguous variant

Behavior:

* form appears to allow email change
* active mutation disabled in fixture config

Expected result:

* candidate with low or medium confidence
* no confirmed finding

Use `juice-shop`, `dvwa`, or `webgoat` only if a controlled fixture account and deterministic email-change/reset flow are available. Do not force this stub onto a fixture that cannot expose email-change state safely.

## Acceptance criteria

Implementation is accepted when:

* The runner performs passive discovery without mutating state by default.
* Active checks run only when RoE and scanner-owned account inputs are present.
* The runner uses shared `ScanTarget` and `Evidence`.
* The runner defines only `EmailChangeAtoSignature` and `EmailChangeAtoFinding` as stub-specific persistence types.
* Detection is deterministic and uses response evidence, state readback, and optional mailbox sink evidence.
* The runner never tests real user accounts.
* The runner never consumes reset links or changes passwords.
* The runner redacts reset tokens, cookies, auth headers, CSRF tokens, and session IDs.
* The runner hashes or redacts email addresses in findings.
* The runner rolls back email changes when mutation occurs.
* Rollback failure stops further mutation and marks the run for review.
* Confirmed findings require explicit evidence IDs.
* Negative cases are tested: current password required, recent reauth required, pending verification, reset tied to old email.
* Candidate findings are used for ambiguous or passive-only evidence.
* The runner handles TLS errors, redirects, JSON/HTML responses, timeouts, and malformed responses gracefully.
* The runner respects request and time budgets.
* The runner is idempotent when repeated against the fixture.
* Tests mock or use local fixtures only.
* No external mailbox or third-party email provider is required for unit tests.
* AI is `None` for this stub.

