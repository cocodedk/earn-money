---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 3
spec: 14
slug: session-mix-up
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 3.14 Session mix-up

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

Detect cases where the application confuses authenticated user identity across sessions, accounts, or login transitions. The runner cares because session mix-up can expose one user's data to another user or keep server-side identity bound to the wrong browser session after account switching.

## Inputs

The runner receives a shared `ScanTarget` and writes shared `Evidence` records. This stub does not redefine either type.

Required inputs:

* `target`: shared `ScanTarget`.
* `base_url`: normalized target origin from `ScanTarget`.
* `http_client`: shared HTTP client with isolated cookie-jar support.
* `scanner_config`: stub-specific knobs listed below.

Required for confirmed testing:

* `test_account_a`: scoped fixture/test account A.
* `test_account_b`: scoped fixture/test account B.
* `login_flow`: known safe login flow.
* `logout_flow`: known logout flow for cleanup and same-browser transition testing.
* `safe_identity_check`: endpoint or page that returns a minimal deterministic identity marker, such as fixture user ID or email hash.

Optional inputs:

* `account_switch_flow`: known product-supported account/workspace switch flow, if explicitly scoped.
* `csrf_extractor`: shared helper for login/logout forms with CSRF tokens.
* `expected_identity_markers`: fixture-configured markers for account A and B.

Config knobs:

| Name | Default | Purpose |
| ---- | ------: | ------- |
| `enabled` | `true` | Allows this stub to run. |
| `allow_login_submission` | `false` | Must be explicitly enabled with two scoped accounts. |
| `allow_logout_submission` | `false` | Must be explicitly enabled with known logout flow. |
| `allow_same_browser_account_switch_test` | `false` | Tests A logout/login B in the same cookie jar. |
| `allow_product_switch_flow_test` | `false` | Tests a configured account/workspace switch flow. |
| `max_login_attempts_per_account` | `1` | Prevents account lockout and noisy auth logs. |
| `max_identity_checks` | `6` | Bounds identity-marker requests. |
| `request_timeout_ms` | `10000` | Per-request timeout. |
| `redact_identity_values` | `true` | User identifiers must be redacted or fingerprinted in logs and findings. |

## Detection logic

Detection is deterministic and compares safe identity markers between two scoped accounts.

### 1. Establish isolated account baselines

Only run when `allow_login_submission=true` and both scoped accounts are available.

1. Create isolated client A with its own cookie jar.
2. Log in as account A.
3. Request `safe_identity_check`.
4. Record account A identity marker as a fingerprint.
5. Create isolated client B with its own cookie jar.
6. Log in as account B.
7. Request `safe_identity_check`.
8. Record account B identity marker as a fingerprint.

Abort if the two accounts do not produce distinct markers. A fixture with indistinguishable identities cannot prove mix-up.

### 2. Same-browser transition test

Only run when `allow_same_browser_account_switch_test=true`, `logout_flow` is known, and both accounts are scoped.

1. Create one isolated client.
2. Log in as account A.
3. Confirm identity marker A.
4. Log out using the known logout flow.
5. Log in as account B in the same client.
6. Confirm identity marker B.
7. Request `safe_identity_check` again after redirects settle.

Vulnerable signals:

* After logging in as B, the safe marker still shows A.
* Response contains mixed A and B identity markers.
* Server returns B cookies but A identity marker.
* Account switch succeeds but subsequent API identity differs from UI identity.

Safe signals:

* Account A and B remain distinct in isolated clients.
* Same-browser transition from A to B shows only B after B login.
* Old A session is not accepted after logout.

### 3. Product switch-flow test

Only run when `allow_product_switch_flow_test=true` and `account_switch_flow` is explicitly configured.

Examples:

* Switching between personal and organization accounts.
* Switching between workspaces where identity marker should change.
* Switching between delegated user sessions in a fixture.

For each configured switch, compare pre-switch and post-switch safe identity markers. Do not discover switch endpoints. Do not attempt unauthorized account linking or tenant switching; those belong to access-control and business-logic specs.

### 4. Status and confidence

| Condition | Status | Confidence |
| --------- | ------ | ---------- |
| Same-browser A-to-B transition leaves A identity active after B login. | `confirmed` | `high` |
| Response contains both account A and B identity markers in an authenticated context. | `confirmed` | `high` |
| Configured switch flow produces identity marker inconsistent with expected account/workspace. | `confirmed` | `high` |
| Identity marker is ambiguous or not distinct between accounts. | `stale` | `low` |
| All isolated and transition checks keep identities distinct. | `rejected` | `high` |
| Test aborted because accounts, safe marker, login/logout flow, or safety precondition is missing. | `stale` | `low` |

Cached private data after logout belongs to spec 3.15. Accessing another user's resources belongs to Phase 4 access-control specs.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Stub-specific types: `SessionMixUpSignature`, `SessionMixUpFinding`.

### `SessionMixUpSignature`

```ts
export interface SessionMixUpSignature {
  signature_id: string;
  flow_kind:
    | "isolated_identity_baseline"
    | "same_browser_account_transition"
    | "product_account_switch";
  login_url: string;
  logout_url?: string;
  identity_check_url: string;
  requires_two_accounts: true;
  confidence: "low" | "medium" | "high";
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
```

### `SessionMixUpFinding`

```ts
export interface SessionMixUpFinding {
  finding_id: string;
  target_id: string;
  evidence_ids: string[];

  flow_kind:
    | "isolated_identity_baseline"
    | "same_browser_account_transition"
    | "product_account_switch";
  login_url: string;
  logout_url?: string;
  identity_check_url: string;

  account_a_marker_fingerprint: string;
  account_b_marker_fingerprint: string;
  observed_marker_fingerprint?: string;

  observation: {
    account_a_authenticated: boolean;
    account_b_authenticated: boolean;
    same_browser_transition_used: boolean;
    product_switch_used: boolean;
    expected_marker: "account_a" | "account_b" | "configured_switch_target";
    observed_marker: "account_a" | "account_b" | "mixed" | "unknown";
    mixed_markers_seen: boolean;
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

* Login request metadata for both accounts with secrets omitted.
* Safe identity marker evidence for account A and B, redacted or fingerprinted.
* Same-browser transition evidence when used.
* Product switch-flow evidence when used.
* Logout cleanup evidence when used.

Recommended remediation:

* Bind server-side session state to one authenticated principal at a time.
* Clear old identity and authorization context during logout, account switch, and login as another account.
* Avoid mixing client-side cached identity with server-side identity decisions.
* Recompute identity and authorization context after every account/workspace switch.
* Add tests for multi-account login/logout transitions.

## Safety

This check is active because it logs in as two scoped accounts and may perform logout or a configured switch flow.

Allowed:

* One login per scoped account for isolated baselines.
* One same-browser A-to-B transition when explicitly enabled.
* One configured product switch flow when explicitly enabled.
* Requests only to `safe_identity_check` for identity proof.
* Cleanup logout when known.

Not allowed:

* Password guessing.
* Username guessing.
* Testing real user accounts not explicitly scoped.
* Discovering or brute forcing account switch endpoints.
* Unauthorized account linking, tenant switching, or delegated-login abuse.
* Fetching arbitrary private resources from either account.
* Using identity marker data beyond comparison.
* Continuing after WAF, abuse detection, lockout, CAPTCHA, MFA challenge, or `429`.

PII and secrets:

* Never log passwords, CSRF tokens, authorization headers, or raw session tokens.
* Redact or fingerprint identity markers.
* Use fixture-only synthetic identifiers where possible.
* Store account markers as fingerprints, not raw emails or user IDs, unless fixture-only.
* Do not send identity or session evidence to AI.

AI involvement: `None`.

There is no deterministic gap that requires AI. Identity marker comparison and flow sequencing are deterministic.

## Pass/fail check

A coding agent implementation passes when these assertions hold.

Positive assertions:

* It accepts a shared `ScanTarget` and writes shared `Evidence`.
* It does not redefine shared `ScanTarget` or `Evidence`.
* It requires two scoped accounts for confirmed testing.
* It uses isolated clients for account A and account B baselines.
* It verifies that account A and B identity markers are distinct before mix-up testing.
* It performs same-browser transition only when explicitly enabled.
* It performs product switch-flow testing only when explicitly configured.
* It creates a `confirmed`, `high` finding when account B login still shows account A identity.
* It creates a `confirmed`, `high` finding when mixed A/B markers appear in one authenticated response.
* It creates a `rejected`, `high` result or no vulnerability finding when identities remain distinct.
* It marks the test `stale`, `low` when markers are ambiguous or preconditions are missing.
* It redacts credentials, CSRF tokens, authorization headers, session values, and identity markers.
* It links each finding to at least one `Evidence` record.

Negative assertions:

* It must not submit guessed usernames or passwords.
* It must not use real accounts unless explicitly scoped.
* It must not brute force account switch endpoints.
* It must not attempt unauthorized tenant or workspace switching.
* It must not fetch arbitrary private resources.
* It must not treat cached private data alone as session mix-up; use spec 3.15.
* It must not treat IDOR evidence as this spec; use Phase 4.
* It must not continue after WAF, abuse detection, lockout, CAPTCHA, MFA challenge, or `429`.
* It must not store raw identity markers or tokens in findings.
* It must not send identity/session evidence to an LLM.

## Test fixtures

Use the synthetic fixture slug: `session-cross-user`.

Required fixture routes:

| Route | Behavior | Expected result |
| ----- | -------- | --------------- |
| `/mixup/safe/login` + `/mixup/safe/logout` + `/mixup/safe/me` | A and B remain distinct in isolated and same-browser transitions. | `rejected`, `high` or no finding |
| `/mixup/stale-principal/login` + `/mixup/stale-principal/logout` + `/mixup/stale-principal/me` | Login B after A logout still returns A identity. | `confirmed`, `high` |
| `/mixup/mixed-markers/login` + `/mixup/mixed-markers/me` | Authenticated response includes both A and B markers after transition. | `confirmed`, `high` |
| `/mixup/switch-safe/login` + `/mixup/switch-safe/switch` + `/mixup/switch-safe/me` | Configured switch updates identity marker correctly. | `rejected`, `high` |
| `/mixup/switch-vulnerable/login` + `/mixup/switch-vulnerable/switch` + `/mixup/switch-vulnerable/me` | Configured switch leaves wrong identity marker active. | `confirmed`, `high` |
| `/mixup/ambiguous-marker/login` + `/mixup/ambiguous-marker/me` | A and B markers are indistinguishable. | `stale`, `low` |

Seeded fixture accounts:

* Account A: `alice@example.invalid`
* Account B: `bob@example.invalid`
* Passwords: fixture-provided secrets
* Safe marker: `/me` returns only synthetic account ID and auth state
* Account and session store reset between tests

Compatibility fixtures:

* `juice-shop`, `dvwa`, and `webgoat` may be used only for exploratory multi-account adapter work.
* Do not make acceptance depend on live apps unless deterministic two-account fixtures are added.

## Acceptance criteria

The implementation is acceptable when:

* The check is deterministic against the fixture.
* It performs no login unless `allow_login_submission=true`.
* It performs no same-browser transition unless `allow_same_browser_account_switch_test=true`.
* It performs no product switch flow unless `allow_product_switch_flow_test=true`.
* It completes within configured login and identity-check budgets.
* It handles missing accounts, missing login/logout flows, missing identity marker, ambiguous markers, redirects, TLS failures, timeouts, and connection errors gracefully.
* It stops on CAPTCHA, MFA challenge without configured fixture secret, lockout, WAF block, abuse detection, or `429`.
* It redacts credentials, CSRF tokens, authorization headers, session values, and identity markers.
* It stores findings with at least one evidence ID.
* It reports `confirmed`, `rejected`, and `stale` statuses correctly.
* It defines only `SessionMixUpSignature` and `SessionMixUpFinding` as stub-specific types.
* Unit tests cover two-account baseline setup, identity-marker fingerprinting, same-browser transition sequencing, product switch gating, mixed-marker detection, redaction, safety aborts, and negative assertions.
* Fixture tests cover safe transition, stale principal, mixed markers, safe switch, vulnerable switch, and ambiguous marker.
* AI is not called.
