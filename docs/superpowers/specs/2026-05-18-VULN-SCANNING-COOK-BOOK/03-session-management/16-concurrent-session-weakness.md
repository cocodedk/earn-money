---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 16
slug: concurrent-session-weakness
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.16 Concurrent session weakness

> Phase 3 — Session management · Category: Cross-user session issues

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

Detect unsafe handling of multiple simultaneous sessions for the same account, including ignored single-session policies, broken "logout all devices" behavior, failed device/session revocation, and old sessions surviving security-sensitive account changes. The runner cares because concurrent-session controls are often the only way a user or administrator can evict stale, shared-device, or compromised sessions.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar support.
* `scanner_config`: stub-specific knobs listed below.

Required for confirmed testing:

* `test_account`: scoped fixture/test account.
* `login_flow`: known safe login flow.
* `safe_authenticated_check`: endpoint or page that returns a synthetic authenticated marker for the test account.
* `concurrent_session_policy`: configured expectation for the target or fixture.

Optional inputs:

* `logout_all_flow`: known "logout all devices" or "sign out everywhere" flow.
* `session_revoke_flow`: known flow to revoke another active session or device.
* `password_change_flow`: scoped password-change flow for a fixture account.
* `session_list_flow`: known account session/device list endpoint or page.
* `csrf_extractor`: shared helper for forms with CSRF tokens.
* `expected_session_marker`: fixture-provided marker for per-session observations, when available.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled with scoped credentials. |
| `allow_second_session_login` | `false` | Permits a second isolated login for the same account. |
| `allow_logout_all_submission` | `false` | Permits a configured logout-all flow. |
| `allow_session_revoke_submission` | `false` | Permits a configured revoke-device/session flow. |
| `allow_password_change_submission` | `false` | Permits a fixture password-change flow. |
| `concurrent_session_policy` | `"unknown"` | One of `"unknown"`, `"multiple_allowed"`, `"single_session"`, `"max_sessions"`, `"logout_all_required"`, `"revoke_other_required"`, `"security_change_revokes_old_sessions"`. |
| `max_expected_sessions` | `1` | Applies only when policy is `"max_sessions"`. |
| `max_login_attempts` | `2` | Bounds valid login submissions. |
| `max_session_checks` | `8` | Bounds safe authenticated-marker requests. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `redact_session_values` | `true` | Cookies, tokens, session IDs, and markers must be redacted or fingerprinted. |

## Detection logic

Detection is deterministic and uses two isolated clients for the same scoped account.

### 1. Establish the first session

Only run when `allow_login_submission=true` and the scoped account is available.

1. Create isolated client A with an empty cookie jar.
2. Log in as the scoped test account.
3. Request `safe_authenticated_check`.
4. Confirm the authenticated marker appears.
5. Record response status, redirects, safe marker fingerprint, and session-cookie metadata.

Abort if login fails, the marker is missing, the account hits MFA/CAPTCHA/lockout, or the response looks like abuse prevention.

### 2. Create the second session

Only run when `allow_second_session_login=true`.

1. Create isolated client B with an empty cookie jar.
2. Log in as the same scoped test account.
3. Request `safe_authenticated_check` from client B.
4. Re-request `safe_authenticated_check` from client A.

Interpretation is policy-driven:

* If policy is `"single_session"`, client A should no longer be authenticated after client B logs in.
* If policy is `"max_sessions"` and `max_expected_sessions=1`, client A should no longer be authenticated after client B logs in.
* If policy is `"multiple_allowed"`, both clients staying authenticated is acceptable and should not produce a finding.
* If policy is `"unknown"`, do not report merely because two sessions are active. Record a `stale` result unless another configured control fails.

Do not create high-volume session counts. This check uses two clients unless the fixture explicitly sets a higher `max_expected_sessions` and still remains within `max_login_attempts`.

### 3. Logout-all verification

Only run when `allow_logout_all_submission=true` and `logout_all_flow` is configured.

1. Keep client A and client B authenticated.
2. Trigger logout-all from the configured client and flow.
3. Re-check the other client with `safe_authenticated_check`.
4. If the flow is supposed to preserve the current session, also verify the initiating client behavior matches the configured expectation.

Vulnerable signal: a non-initiating session remains authenticated after a completed logout-all action.

### 4. Session/device revocation verification

Only run when `allow_session_revoke_submission=true`, `session_revoke_flow` is configured, and the fixture exposes a safe way to identify client A or B.

1. Establish two sessions.
2. Use `session_list_flow` or fixture metadata to identify the target session without exposing raw session IDs.
3. Revoke the other session using the configured flow.
4. Re-check the revoked client and the initiating client.

Vulnerable signal: the revoked client remains authenticated while the revoke action reports success.

### 5. Security-change invalidation verification

Only run when `allow_password_change_submission=true`, `password_change_flow` is configured, and the fixture account can be safely reset after the test.

1. Establish two sessions.
2. Change the password or configured security property from one client.
3. Re-check the old second session.
4. Reset the fixture credential using the fixture cleanup flow.

Only treat surviving sessions as a finding when `concurrent_session_policy` is `"security_change_revokes_old_sessions"` or the fixture explicitly requires old-session invalidation after that change.

### 6. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Policy requires single active session, but client A remains authenticated after client B login. | `confirmed` | `high` |
| Policy requires `max_expected_sessions=1`, but both clients remain authenticated after second login. | `confirmed` | `high` |
| Configured logout-all reports success, but another session remains authenticated. | `confirmed` | `high` |
| Configured revoke-session action reports success, but revoked session remains authenticated. | `confirmed` | `high` |
| Policy requires old-session invalidation after password/security change, but old session remains authenticated. | `confirmed` | `high` |
| A configured control appears to request old-session invalidation, but the success response or exact invalidation target is ambiguous and an old session remains authenticated. | `candidate` | `medium` |
| Multiple sessions remain active while policy is unknown. | `stale` | `low` |
| Multiple sessions remain active while policy is explicitly multiple-session allowed. | `rejected` | `high` |
| All configured concurrent-session controls enforce the expected state. | `rejected` | `high` |
| Test aborted because account, login flow, safe marker, configured control, or safety precondition is missing. | `stale` | `low` |

Do not classify a lack of session-management UI as a confirmed vulnerability by itself. Report only deterministic enforcement failures against configured policy or fixture behavior.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `ConcurrentSessionWeaknessSignature`, `ConcurrentSessionWeaknessFinding`.

### `ConcurrentSessionWeaknessSignature`

```ts
export interface ConcurrentSessionWeaknessSignature {
  signature_id: string;
  check_kind:
    | "second_login_policy"
    | "logout_all"
    | "session_revoke"
    | "security_change_invalidation";
  login_url: string;
  authenticated_check_url: string;
  control_url?: string;
  concurrent_session_policy:
    | "unknown"
    | "multiple_allowed"
    | "single_session"
    | "max_sessions"
    | "logout_all_required"
    | "revoke_other_required"
    | "security_change_revokes_old_sessions";
  max_expected_sessions?: number;
  requires_valid_credentials: true;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `ConcurrentSessionWeaknessFinding`

```ts
export interface ConcurrentSessionWeaknessFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  check_kind:
    | "second_login_policy"
    | "logout_all"
    | "session_revoke"
    | "security_change_invalidation";
  login_url: string;
  authenticated_check_url: string;
  control_url?: string;

  concurrent_session_policy:
    | "unknown"
    | "multiple_allowed"
    | "single_session"
    | "max_sessions"
    | "logout_all_required"
    | "revoke_other_required"
    | "security_change_revokes_old_sessions";
  max_expected_sessions?: number;

  session_observation: {
    client_a_authenticated_before_control: boolean;
    client_b_authenticated_before_control: boolean;
    client_a_authenticated_after_control: boolean;
    client_b_authenticated_after_control: boolean;
    initiating_client: "client_a" | "client_b" | "none";
    revoked_client?: "client_a" | "client_b";
    control_reported_success: boolean;
    old_session_should_be_invalidated: boolean;
  };

  marker_fingerprints: {
    client_a_marker?: string;
    client_b_marker?: string;
    revoked_session_marker?: string;
  };

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

* Login request metadata for client A and client B with secrets omitted.
* Safe authenticated-marker evidence for both clients before and after the tested control.
* Configured policy or fixture expectation evidence.
* Logout-all, revoke-session, or password-change evidence when those flows are used.
* Cleanup/reset evidence for password-change fixtures.

Recommended remediation:

* Enforce the documented concurrent-session policy server-side, not only in the UI.
* Invalidate replaced sessions immediately when single-session or max-session policy is active.
* Make logout-all and session/device revocation invalidate server-side session records, refresh tokens, and remember-me tokens together.
* Invalidate or re-authenticate old sessions after password changes, MFA resets, recovery changes, and other account-security events where policy requires it.
* Add audit logs and tests that verify the old session fails on the next authenticated request.

## Safety

This check is active because it logs in and may submit account/session control actions.

Allowed:

* Up to `max_login_attempts` valid login submissions for one scoped test account, default two.
* Safe authenticated-marker requests for the same account.
* Configured logout-all, revoke-session, or password-change flows when explicitly enabled.
* Fixture credential reset after password-change tests.

Not allowed:

* Password guessing.
* Username guessing.
* Testing real user accounts not explicitly scoped.
* Creating many sessions to stress limits.
* Enumerating session IDs, devices, users, or tenants.
* Revoking sessions for accounts outside the scoped fixture account.
* Bypassing MFA, recovery, or device verification.
* Using stolen, leaked, or externally supplied tokens.
* Continuing after WAF, abuse detection, lockout, CAPTCHA, MFA challenge, or `429`.

PII and secrets:

* Never log passwords, CSRF tokens, authorization headers, raw cookies, raw tokens, or raw session IDs.
* Redact or fingerprint authenticated markers and per-session markers.
* Store only the minimum evidence needed to prove the state transition.
* Do not store screenshots containing real private data.
* Do not send session evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Policy matching, marker comparison, and session-state transitions are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It uses two isolated cookie jars or browser contexts for the same scoped account.
* It requires `allow_login_submission=true` before submitting credentials.
* It requires `allow_second_session_login=true` before creating the second session.
* It does not report active concurrent sessions as vulnerable when policy is `"unknown"`.
* It reports `confirmed`, `high` when policy requires one active session and the old session remains authenticated after a second login.
* It reports `rejected`, `high` when policy explicitly allows multiple sessions and both sessions remain active.
* It performs logout-all checks only when the configured flow and enable flag are present.
* It reports `confirmed`, `high` when logout-all reports success but another session remains authenticated.
* It performs revoke-session checks only when the configured flow and enable flag are present.
* It reports `confirmed`, `high` when a revoked session remains authenticated after a successful revoke action.
* It performs password/security-change invalidation checks only when explicitly enabled and fixture reset is available.
* It links each finding to policy evidence and at least one before/after authenticated-marker evidence record.
* It redacts credentials, CSRF tokens, authorization headers, raw cookies, raw tokens, raw session IDs, and markers.

Negative assertions:

* It must not guess usernames or passwords.
* It must not create high-volume sessions to discover limits.
* It must not infer a vulnerability from multiple active sessions without a configured policy or fixture expectation.
* It must not enumerate session IDs, devices, users, or tenants.
* It must not revoke sessions outside the scoped fixture account.
* It must not run password-change tests without a fixture reset path.
* It must not bypass MFA, recovery, or device-verification prompts.
* It must not store raw credentials, cookies, tokens, session IDs, or private markers.
* It must not continue after WAF, abuse detection, lockout, CAPTCHA, MFA challenge, or `429`.
* It must not send session evidence to an LLM.

## Test fixtures

Use the synthetic fixture slug: `session-concurrency`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/concurrent/single-session-vulnerable/login` + `/concurrent/single-session-vulnerable/me` | Policy requires one session, but old session survives second login. | `confirmed`, `high` |
| `/concurrent/single-session-safe/login` + `/concurrent/single-session-safe/me` | Policy requires one session and old session is invalidated. | `rejected`, `high` |
| `/concurrent/multiple-allowed/login` + `/concurrent/multiple-allowed/me` | Policy allows multiple sessions. | `rejected`, `high` |
| `/concurrent/unknown-policy/login` + `/concurrent/unknown-policy/me` | Two sessions remain active with no configured policy. | `stale`, `low` |
| `/concurrent/logout-all-vulnerable/login` + `/concurrent/logout-all-vulnerable/logout-all` + `/concurrent/logout-all-vulnerable/me` | Logout-all reports success but other session survives. | `confirmed`, `high` |
| `/concurrent/logout-all-safe/login` + `/concurrent/logout-all-safe/logout-all` + `/concurrent/logout-all-safe/me` | Logout-all invalidates other sessions. | `rejected`, `high` |
| `/concurrent/revoke-vulnerable/login` + `/concurrent/revoke-vulnerable/sessions` + `/concurrent/revoke-vulnerable/revoke` + `/concurrent/revoke-vulnerable/me` | Revoke reports success but revoked session survives. | `confirmed`, `high` |
| `/concurrent/revoke-safe/login` + `/concurrent/revoke-safe/sessions` + `/concurrent/revoke-safe/revoke` + `/concurrent/revoke-safe/me` | Revoke invalidates selected session. | `rejected`, `high` |
| `/concurrent/password-change-vulnerable/login` + `/concurrent/password-change-vulnerable/password` + `/concurrent/password-change-vulnerable/me` | Policy requires old-session invalidation after password change, but old session survives. | `confirmed`, `high` |
| `/concurrent/password-change-safe/login` + `/concurrent/password-change-safe/password` + `/concurrent/password-change-safe/me` | Password change invalidates old sessions and fixture resets credential. | `rejected`, `high` |
| `/concurrent/rate-limited/login` | Fixture returns `429` or abuse signal after configured threshold. | `stale`, `low`; scanner stops |

Seeded fixture account:

* Username: `alice@example.invalid`
* Password: fixture-provided secret
* Authenticated marker: synthetic account-only string
* Optional session marker: synthetic per-session string
* Account, password, and session store reset between tests

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used only for exploratory observations where explicit policy is configured.
* Do not make acceptance depend on live apps unless deterministic concurrent-session fixtures are added.

## Acceptance criteria

The implementation is acceptable when:

* The check is deterministic against the fixture.
* It performs no login unless `allow_login_submission=true`.
* It creates no second session unless `allow_second_session_login=true`.
* It performs no logout-all action unless `allow_logout_all_submission=true`.
* It performs no session revoke action unless `allow_session_revoke_submission=true`.
* It performs no password/security-change action unless `allow_password_change_submission=true` and a reset path is available.
* It submits no more than `max_login_attempts` and performs no more than `max_session_checks`.
* It handles missing account, missing login flow, missing safe marker, missing policy, missing configured control, redirects, TLS failures, timeouts, and connection errors gracefully.
* It stops on CAPTCHA, MFA challenge without configured fixture secret, lockout, WAF block, abuse detection, or `429`.
* It redacts credentials, CSRF tokens, authorization headers, cookies, tokens, session IDs, and markers.
* It stores findings with policy evidence and at least one before/after evidence ID.
* It reports `confirmed`, `rejected`, and `stale` statuses correctly and uses `candidate` only for explicitly configured ambiguous policy transitions.
* It defines only `ConcurrentSessionWeaknessSignature` and `ConcurrentSessionWeaknessFinding` as stub-specific types.
* Unit tests cover policy interpretation, isolated client handling, second-login invalidation, multiple-session allowed rejection, unknown-policy stale result, logout-all invalidation, revoke-session invalidation, password-change invalidation, credential reset gating, redaction, safety aborts, and negative assertions.
* Fixture tests cover single-session vulnerable/safe, multiple-allowed, unknown-policy, logout-all vulnerable/safe, revoke vulnerable/safe, password-change vulnerable/safe, and rate-limit abort behavior.
* AI is not called.
