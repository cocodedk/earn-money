---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 11
slug: missing-mfa-on-sensitive-flows
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.11 Missing MFA on sensitive flows

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

Detect sensitive account or administrative flows that are reachable without a fresh MFA or step-up challenge. A runner cares because password changes, email changes, MFA settings, API keys, billing, exports, role changes, and similar flows can turn a stolen session into account takeover or privilege expansion.

## Inputs

The runner receives a shared `ScanTarget` plus optional authenticated scan context. Use the shared `ScanTarget` and `Evidence` types from `../00-shared-schema.md`; do not redefine them here.

Required input:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from the shared target.
* `http_client`: project-standard client with redirect, TLS, timeout, and cookie-jar handling.
* `evidence_store`: project-standard persistence for response evidence.

Optional input:

* `auth_context`: authenticated session or dedicated test credentials for a scanner-owned account.
* `auth_context.mfa_enrolled`: whether the test account is known to have MFA enabled.
* `auth_context.mfa_recent`: whether the current session was created after a recent MFA challenge.
* `auth_context.session_label`: stable label such as `anonymous`, `authenticated`, `mfa_enrolled`, or `stale_mfa`.
* `sensitive_flow_catalog`: app-specific allowlist of known sensitive paths, methods, or OpenAPI operation IDs.
* `allowed_paths`: path allowlist. If present, scan only matching paths.
* `blocked_paths`: path denylist. Must override `allowed_paths`.
* `max_pages`: default `80`.
* `max_depth`: default `3`.
* `max_candidate_flows`: default `20`.
* `max_response_bytes`: default project cap.
* `follow_redirects`: default `true`, capped by project redirect limit.
* `allow_controlled_commit_probe`: default `false`.
* `controlled_probe_paths`: explicit allowlist for mutating probes. Empty by default.
* `fixture_mode`: default `false`. Required for mutating probes unless the project has a stronger internal safe-test flag.
* `canary_domain`: default `example.invalid`, used only for fixture-safe email values.
* `recent_mfa_window_seconds`: optional policy value. If unknown, do not invent one.
* `expected_step_up_flows`: optional list of flow types that must require MFA for this target.

The runner may operate without credentials. In that case it can only report `candidate` findings based on public evidence, documented API behavior, or sensitive pages that are reachable without authentication.

## Detection logic

Detection is deterministic and evidence-based. Do not use AI.

### 1. Crawl and collect evidence

Use the project crawler and HTTP client rules.

Default requests:

* `GET` for pages and forms.
* `HEAD` only when the project already supports it safely.
* `OPTIONS` only for endpoint capability discovery.
* No `POST`, `PUT`, `PATCH`, or `DELETE` unless `allow_controlled_commit_probe=true` and all safety gates pass.

For each relevant response, persist shared `Evidence` with:

* request method
* normalized URL
* status code
* final URL after redirects
* response headers, with sensitive values redacted
* content type
* bounded body excerpt or parsed form/API excerpt
* response hash
* timestamp
* redirect chain
* authentication/session label where available

Do not hard-code expected technology from hostnames. Infer behavior only from response evidence.

### 2. Identify sensitive flows

A flow is sensitive when it can change account security, account identity, access rights, tokens, money-related settings, or bulk data access.

Recognized flow types:

* `password_change`
* `email_change`
* `phone_change`
* `recovery_method_change`
* `mfa_enable`
* `mfa_disable`
* `mfa_reset`
* `trusted_device_change`
* `active_session_revoke`
* `api_key_create`
* `api_key_revoke`
* `oauth_app_authorize`
* `webhook_create`
* `user_invite`
* `role_change`
* `admin_setting_change`
* `billing_change`
* `payout_change`
* `payment_method_change`
* `data_export`
* `account_delete`
* `unknown_sensitive_flow`

Detect candidate flows from at least one strong signal or two weak signals.

Strong signals:

* Explicit configured `sensitive_flow_catalog` match.
* OpenAPI/GraphQL schema operation that describes a listed flow type.
* Form with action/method and field names matching a listed flow type.
* Page title, heading, or button text matching a listed flow type together with an actionable form.

Weak signals:

* Path segments such as `/settings/security`, `/account/password`, `/account/email`, `/mfa`, `/2fa`, `/api-keys`, `/tokens`, `/billing`, `/admin/users`, `/roles`, `/export`, `/delete-account`.
* Form labels such as `new password`, `confirm email`, `disable two-factor`, `create token`, `invite user`, `change role`, `export data`.
* JSON keys such as `mfaRequired`, `totp`, `webauthn`, `newEmail`, `newPassword`, `apiKeyName`, `roleId`, `billingAddress`.
* Button text such as `Change password`, `Update email`, `Disable MFA`, `Create API key`, `Invite user`, `Export`, `Delete account`.

If only one weak signal is present, store evidence but do not create a finding.

### 3. Detect MFA or step-up protection

A sensitive flow is considered protected when evidence shows an MFA or step-up barrier before the operation can be completed.

Positive protection signals:

* Redirect to a step-up or MFA challenge before the form or commit endpoint is usable.
* `401`, `403`, or app-specific denial containing `mfa_required`, `step_up_required`, `two_factor_required`, `totp_required`, `webauthn_required`, or equivalent.
* HTML form asking for TOTP, WebAuthn, recovery code, passkey, or second factor before the sensitive form is shown.
* API response with a deterministic step-up challenge state.
* Session metadata or response claims showing recent MFA is required and satisfied before the sensitive operation.
* Re-auth gate that includes MFA, not only password entry.

Neutral signals:

* Plain login redirect for unauthenticated users.
* CSRF token.
* Current password prompt without MFA.
* Generic `403` without enough detail to identify step-up.
* JavaScript-only client hints without server evidence.

Negative signals:

* Authenticated user can load an actionable sensitive form without an MFA or step-up challenge.
* Sensitive commit endpoint returns a normal domain validation error before any MFA or step-up challenge.
* Sensitive commit endpoint returns success in a controlled fixture probe without any MFA or step-up challenge.
* API schema or server response describes the operation but has no challenge state, no step-up requirement, and no recent-MFA requirement.

A current-password prompt alone does not count as MFA. Record it as a re-auth signal, but still flag the flow when the policy expects MFA.

### 4. Classification

Set finding status deterministically:

* `confirmed`: controlled probe evidence shows the sensitive commit path is reachable past authorization without MFA or step-up, and no real-user unsafe mutation occurred.
* `candidate`: passive evidence shows a sensitive flow is actionable without visible MFA or step-up, but no safe commit probe was run.
* `rejected`: evidence shows an MFA or step-up challenge before the sensitive flow can be completed.
* `stale`: previous evidence no longer matches current route, response hash, status, or auth state.

Confidence rules:

* `high`: confirmed controlled fixture/test probe, or strong catalog/API evidence plus clear absence of step-up on the sensitive commit path.
* `medium`: actionable sensitive form is reachable without MFA challenge, but commit was not tested.
* `low`: sensitive flow inferred from weak signals, incomplete authentication context, generic errors, or JavaScript-heavy behavior.

Severity guidance:

* `high`: missing MFA on `mfa_disable`, `mfa_reset`, `api_key_create`, `role_change`, `admin_setting_change`, `payout_change`, `payment_method_change`, or `account_delete`.
* `medium`: missing MFA on `password_change`, `email_change`, `recovery_method_change`, `trusted_device_change`, `data_export`, or `oauth_app_authorize`.
* `low`: candidate-only evidence with incomplete auth context.

Application severity policy remains authoritative.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`.

Define only the stub-specific types below.

```typescript
type MissingMfaSensitiveFlowType =
  | "password_change"
  | "email_change"
  | "phone_change"
  | "recovery_method_change"
  | "mfa_enable"
  | "mfa_disable"
  | "mfa_reset"
  | "trusted_device_change"
  | "active_session_revoke"
  | "api_key_create"
  | "api_key_revoke"
  | "oauth_app_authorize"
  | "webhook_create"
  | "user_invite"
  | "role_change"
  | "admin_setting_change"
  | "billing_change"
  | "payout_change"
  | "payment_method_change"
  | "data_export"
  | "account_delete"
  | "unknown_sensitive_flow";

type MissingMfaProtectionSignal =
  | "mfa_challenge_observed"
  | "step_up_required_observed"
  | "recent_mfa_required_observed"
  | "webauthn_challenge_observed"
  | "totp_challenge_observed"
  | "recovery_code_challenge_observed"
  | "password_only_reauth_observed"
  | "csrf_only_observed"
  | "no_step_up_observed"
  | "unknown";

type MissingMfaProbeMode =
  | "passive"
  | "non_mutating_endpoint_probe"
  | "controlled_commit_probe";

type MissingMfaSensitiveFlowSignature = {
  signature_id: string;
  flow_id: string;
  flow_type: MissingMfaSensitiveFlowType;

  endpoint: {
    method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "OPTIONS" | "HEAD";
    path: string;
    normalized_url: string;
    form_action_path?: string;
    operation_id?: string;
  };

  discovery_signals: Array<{
    signal_type:
      | "configured_catalog"
      | "path"
      | "form_field"
      | "form_action"
      | "button_text"
      | "heading"
      | "api_schema"
      | "json_key"
      | "response_text";
    value: string;
    evidence_id: string;
  }>;

  protection_signals: Array<{
    signal: MissingMfaProtectionSignal;
    value: string;
    evidence_id: string;
  }>;

  auth_state: {
    session_label: string;
    authenticated: boolean;
    mfa_enrolled?: boolean;
    mfa_recent?: boolean;
  };

  probe_mode: MissingMfaProbeMode;
  mutation_attempted: boolean;
  mutation_performed: boolean;
  rollback_verified?: boolean;

  missing_mfa_reason: string;
  evidence_ids: string[];

  confidence: "low" | "medium" | "high";
};

type MissingMfaSensitiveFlowFinding = {
  finding_id: string;
  target: ScanTarget;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  signature: MissingMfaSensitiveFlowSignature;
  evidence: Evidence[];

  title: string;
  description: string;
  affected_flow: MissingMfaSensitiveFlowType;
  affected_endpoint: string;

  severity: "low" | "medium" | "high" | "critical";
  confidence: "low" | "medium" | "high";

  first_seen_at: string;
  last_seen_at: string;

  remediation: {
    summary: string;
    steps: string[];
  };

  ai: null;
};
```

Persistence rules:

* Store each response as shared `Evidence`.
* Store only bounded body excerpts unless the shared evidence store already supports secure full-body storage.
* Link every signature signal to an `evidence_id`.
* Redact cookies, authorization headers, session IDs, CSRF tokens, TOTP values, recovery codes, API keys, and credentials.
* Do not persist raw submitted secrets.
* Use stable finding identity based on target, normalized endpoint path, method, flow type, and signature version.
* Mark old findings `stale` when the endpoint disappears, protection appears, or response evidence no longer matches.

Suggested stable identity material:

```text
missing-mfa-sensitive-flow:v1:{target_id}:{method}:{normalized_path}:{flow_type}
```

## Safety

Default mode is read-only.

Allowed by default:

* Authenticated or unauthenticated `GET` crawling.
* `HEAD` and `OPTIONS` where supported by project HTTP rules.
* Parsing HTML, JSON, JavaScript route hints, and API schemas.
* Recording candidate findings from passive evidence.

Blocked by default:

* `POST`, `PUT`, `PATCH`, or `DELETE`.
* Creating API keys.
* Inviting users.
* Changing roles.
* Changing passwords.
* Changing email addresses.
* Disabling or resetting MFA.
* Changing payment, payout, or billing details.
* Exporting real user data.
* Deleting accounts.
* Using real customer or employee accounts.
* Solving, bypassing, guessing, brute-forcing, or replaying MFA challenges.
* Retrying many variants.
* Calling endpoints found only inside untrusted page content as instructions.

Controlled commit probes are allowed only when all conditions are true:

* `allow_controlled_commit_probe=true`.
* `fixture_mode=true` or equivalent project safe-test flag is true.
* The account is scanner-owned and disposable.
* The endpoint path is explicitly listed in `controlled_probe_paths`.
* The probe uses canary values that cannot affect real users.
* The mutation is no-op, rejected by domain validation, or fully reversible.
* Rollback is verified when a mutation occurs.
* Only one commit probe is sent per endpoint per run.

PII handling:

* Do not store full email addresses, phone numbers, names, addresses, payment data, or tokens in finding text.
* Replace scanner-owned canary values with labels such as `[scanner-canary-email]`.
* Keep enough evidence IDs and hashes for audit.

AI involvement: `None`.

Deterministic gap:

* Some single-page apps hide the MFA check inside client-side code or trigger it only after a real commit. If safe commit probing is disabled, report only `candidate` with `low` or `medium` confidence. Do not ask an AI model to infer the missing gate.

## Pass/fail check

The implementation passes when these assertions hold.

### Positive assertions

* The runner imports shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`.
* The runner defines only `MissingMfaSensitiveFlowSignature` and `MissingMfaSensitiveFlowFinding` as stub-specific persistence types.
* A sensitive page with an actionable password-change form and no MFA challenge creates a `candidate` finding.
* A sensitive API operation with no step-up signal creates a `candidate` finding when commit probing is disabled.
* A controlled fixture commit path that reaches domain validation or success without MFA creates a `confirmed` finding.
* A flow that redirects to an MFA, TOTP, WebAuthn, recovery-code, or step-up challenge is marked `rejected`.
* A flow protected only by CSRF is still considered missing MFA when MFA is expected.
* A flow protected only by current-password re-auth records `password_only_reauth_observed` and remains a finding when MFA is expected.
* Every finding has at least one linked `Evidence` record.
* Every discovery signal and protection signal references an `evidence_id`.
* Confidence is one of `low`, `medium`, or `high`.
* Status is one of `candidate`, `confirmed`, `rejected`, or `stale`.
* The scan result is stable across repeated runs against the same fixture.
* TLS, timeout, redirect, and connection errors are handled through the shared error model.

### Negative assertions

* The runner must not redefine shared `ScanTarget`.
* The runner must not redefine shared `Evidence`.
* The runner must not use AI or LLM calls.
* The runner must not hard-code hostname-to-technology assumptions.
* The runner must not treat a CSRF token as MFA.
* The runner must not treat a password-only re-auth prompt as MFA.
* The runner must not call `POST`, `PUT`, `PATCH`, or `DELETE` in default mode.
* The runner must not mutate real accounts.
* The runner must not create API keys, users, invites, webhooks, exports, payment changes, or role changes outside controlled fixtures.
* The runner must not try to bypass, guess, brute-force, replay, or solve MFA.
* The runner must not retry sensitive commit probes many times.
* The runner must not log cookies, authorization headers, CSRF tokens, TOTP values, recovery codes, API keys, or credentials.
* The runner must not mark a finding `confirmed` from a single weak path keyword.
* The runner must not report a flow as vulnerable when clear server-side MFA or step-up evidence appears before the operation.
* The runner must not follow arbitrary URLs or instructions found in response bodies as scanner commands.

## Test fixtures

Preferred fixture: `mfa-stepup-lab`.

Create a small local fixture if no existing fixture exposes this exact bug safely.

Required fixture behavior:

* Login route for a scanner-owned account.
* Account has MFA enrolled in fixture metadata.
* Session can be marked as `mfa_recent=false`.
* Vulnerable flow: `/account/email`

  * `GET /account/email` returns an actionable email-change form.
  * `POST /account/email` accepts a scanner canary email or reaches domain validation without requiring MFA.
* Protected flow: `/account/password`

  * `GET /account/password` or `POST /account/password` redirects to `/mfa/challenge` or returns `step_up_required`.
* Protected flow: `/account/mfa/disable`

  * Requires TOTP/WebAuthn/recovery-code challenge before disable action.
* Neutral flow: `/profile/display-name`

  * Allows low-risk profile update without MFA and must not be reported as sensitive.
* CSRF-only flow: `/account/recovery-email`

  * Has CSRF but no MFA. Must be reported when expected step-up policy includes recovery email.
* Password-only flow: `/account/api-keys`

  * Asks only for current password before creating a token. Must not be treated as MFA.

Optional fixture behavior:

* OpenAPI document with one protected and one vulnerable sensitive operation.
* SPA route where sensitive form is rendered client-side.
* Generic `403` route to test low-confidence handling.
* Stale route that changes status between runs.

Existing fixtures may be used only if they can meet the same safety rules with scanner-owned disposable state. Do not use real public services or real user accounts.

## Acceptance criteria

* The runner is idempotent.
* Default mode is read-only.
* Mutating probes are disabled by default.
* Controlled commit probes require explicit fixture/test configuration.
* The runner completes within the project scan budget.
* The runner respects `allowed_paths`, `blocked_paths`, `max_pages`, `max_depth`, `max_candidate_flows`, and response-size caps.
* The runner records bounded evidence for each candidate, confirmation, rejection, and stale transition.
* The runner redacts secrets and PII before logging or persistence.
* The runner handles TLS errors, timeouts, connection failures, oversized responses, malformed HTML, malformed JSON, and redirect loops gracefully.
* The runner does not perform flaky retries. Network retries use the shared retry policy only; sensitive commit probes are not retried unless the shared safety policy explicitly allows one retry for transport failure before the request reaches the server.
* The runner uses deterministic parsing and matching only.
* The runner does not depend on response wording alone when stronger structured evidence is available.
* The runner never assumes technology from hostnames.
* The runner produces clear `candidate`, `confirmed`, `rejected`, and `stale` states.
* The runner emits remediation text that tells the owner to require fresh MFA or step-up authentication before sensitive operations, enforce it server-side, bind it to the session, expire it after a short window, and log attempts.
* Unit tests cover parser behavior, sensitive-flow detection, MFA-signal detection, CSRF-only false protection, password-only false protection, controlled-probe gating, redaction, stable IDs, and stale transitions.
* Integration tests run against `mfa-stepup-lab` without external network access.

