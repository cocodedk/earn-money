---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 10
slug: bypass
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.10 Bypass

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

Detect whether an application allows a user who has passed primary authentication but has not completed MFA to access protected routes or perform protected actions. The runner cares because MFA is often implemented as an extra page instead of an enforced authorization state. A bypass exists when the server accepts requests that should require `mfa_verified=true`, not when the UI merely hides those routes.

## Inputs

The runner receives a `ScanTarget` plus an MFA test configuration.

Required inputs:

* `target`: shared `ScanTarget`.
* `primary_credentials`: operator-provided test account credentials.
* `mfa_state`: whether the test account is expected to have MFA enabled.
* `login_paths`: optional known login paths. If omitted, discovery may use shared authentication route discovery.
* `mfa_challenge_paths`: optional known MFA challenge paths.
* `protected_paths`: optional list of routes that should require completed MFA.
* `protected_action_specs`: optional list of safe protected actions to test.
* `max_requests`: request budget for this check.
* `timeout_ms`: per-request timeout.
* `follow_redirects`: default `false` for decision requests so redirects are visible.
* `fixture_mode`: enables safe fixture-only mutations when the target is a local vulnerable app.

Optional inputs:

* `session_cookie_names`: hints only. Do not assume a cookie name means the session is authenticated.
* `csrf_token_selectors`: selectors or response patterns for extracting anti-CSRF tokens from test fixture pages.
* `expected_mfa_indicators`: text or status hints that identify an MFA challenge page.
* `known_authenticated_probe_path`: a harmless path that confirms the primary login session.
* `known_mfa_required_probe_path`: a harmless path that should require completed MFA.
* `allowed_methods`: default `GET, HEAD, OPTIONS`. `POST` is allowed only for explicitly configured fixture-safe protected actions.

Credential rules:

* Use only operator-provided test accounts.
* Do not use real user accounts.
* Do not try to guess, brute force, intercept, or reuse MFA codes.
* Do not attempt phishing, push fatigue, SIM swap, recovery-code guessing, or social flows.
* Do not create accounts unless the shared fixture harness already supports safe account provisioning.

## Detection logic

Detection is deterministic and based on HTTP state transitions. The runner compares server behavior before MFA, after primary authentication, and after completed MFA only when a safe fixture or operator-provided MFA completion hook exists.

### State model

Track these states separately:

1. `anonymous`: no authenticated session.
2. `primary_authenticated_mfa_pending`: valid primary login, MFA challenge not completed.
3. `mfa_verified`: MFA completed through a safe fixture hook or operator-provided test flow.
4. `unknown`: state could not be proven from response evidence.

A finding is only confirmed when the runner proves that a protected resource or action succeeds in state `primary_authenticated_mfa_pending`.

### Baseline discovery

1. Start with a fresh client and no cookies.
2. Request the login page or configured login endpoint.
3. Save response status, redirect target, cookies set, relevant headers, and body excerpt as `Evidence`.
4. Submit primary credentials only if they were provided by the operator.
5. Do not submit an MFA code.
6. Record the next response:

   * MFA challenge page,
   * redirect to MFA challenge,
   * API response requiring MFA,
   * authenticated landing page,
   * failure or unknown state.

The runner must not infer a bypass from landing on a dashboard alone. Some applications show limited dashboards before MFA. A bypass requires access to a route or action that should be MFA-gated.

### Protected route probes

For each configured or discovered protected path:

1. Request the path as `anonymous`.
2. Request the same path as `primary_authenticated_mfa_pending`.
3. If a safe `mfa_verified` state exists, request the same path after MFA completion.
4. Compare server responses.

A route is treated as protected when one or more of these are true:

* It is explicitly listed in `protected_paths`.
* It is identified by fixture metadata as requiring MFA.
* It returns sensitive authenticated content only after completed MFA.
* It performs or exposes account, admin, billing, token, security, or profile-change functionality.
* It is a known security settings route, such as MFA management, password change, API keys, recovery codes, email change, or session management.

### Success signals

A pending-MFA request is suspicious when it receives one or more of:

* `2xx` response with protected content.
* `3xx` redirect to an authenticated protected page, not to MFA or login.
* API response showing a successful protected action.
* Response body contains authenticated-only controls, identifiers, or state for the protected feature.
* Response header or JSON field indicates the request was accepted.
* Different authorization result than anonymous and similar result to `mfa_verified`.

### Non-bypass signals

A pending-MFA request is not a bypass when it receives one or more of:

* `401 Unauthorized`.
* `403 Forbidden`.
* Redirect to login.
* Redirect to MFA challenge.
* JSON error such as `mfa_required`, `step_up_required`, `verification_required`, or equivalent.
* A limited pre-MFA page that does not expose or perform protected functionality.
* A CSRF failure that prevents reaching the authorization decision.

### Common deterministic checks

The runner should support these safe checks when configured:

* Direct navigation to protected route while MFA is pending.
* API request to protected endpoint while MFA is pending.
* Reuse of pre-MFA session cookie against protected route.
* Attempt to skip the MFA challenge URL and request the post-MFA landing route.
* Attempt to access security settings while MFA is pending.
* Attempt to access account email change route while MFA is pending, using `GET` only unless fixture-safe mutation is enabled.
* Attempt to access API key or token management route while MFA is pending, using `GET` only.
* Attempt to access admin route while MFA is pending, using `GET` only.

The runner must not:

* Guess MFA codes.
* Reuse leaked recovery codes.
* Abuse remembered-device cookies from real users.
* Manipulate server-side state outside the test account.
* Generate destructive or externally visible actions.
* Treat client-side route access alone as a confirmed bypass.

### Classification

Use these classifications:

* `confirmed`: protected route or safe protected action succeeds before MFA completion.
* `candidate`: evidence suggests protected access before MFA, but the protected nature of the route or action is not fully proven.
* `rejected`: pending-MFA state is blocked or redirected to MFA/login.
* `stale`: previous evidence no longer reproduces.

Confidence rules:

* `high`: anonymous is blocked, pending-MFA succeeds, and either fixture metadata or verified-MFA baseline proves the route is protected.
* `medium`: pending-MFA succeeds and route appears sensitive, but no verified-MFA baseline exists.
* `low`: behavior differs from anonymous but protected impact is uncertain.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only stub-specific types:

```ts
export type MfaBypassProbeState =
  | "anonymous"
  | "primary_authenticated_mfa_pending"
  | "mfa_verified"
  | "unknown";

export type MfaBypassProbeMethod = "GET" | "HEAD" | "OPTIONS" | "POST";

export type MfaBypassDecision =
  | "blocked"
  | "mfa_required"
  | "login_required"
  | "protected_access_granted"
  | "protected_action_accepted"
  | "csrf_blocked"
  | "unknown";

export interface MfaBypassSignature {
  id: string;
  target_id: ScanTarget["id"];
  route: string;
  method: MfaBypassProbeMethod;
  expected_gate: "mfa_required" | "step_up_required";
  probe_state: MfaBypassProbeState;
  anonymous_decision?: MfaBypassDecision;
  pending_mfa_decision: MfaBypassDecision;
  verified_mfa_decision?: MfaBypassDecision;
  status_code: number;
  redirect_location?: string;
  response_fingerprint: string;
  matched_indicators: string[];
  evidence_ids: Evidence["id"][];
}

export interface MfaBypassFinding {
  id: string;
  target_id: ScanTarget["id"];
  signature_id: MfaBypassSignature["id"];
  title: string;
  route: string;
  method: MfaBypassProbeMethod;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  severity: "medium" | "high" | "critical";
  summary: string;
  evidence_ids: Evidence["id"][];
  first_seen_at: string;
  last_seen_at: string;
  remediation: string;
}
```

Persistence requirements:

* Store one `Evidence` item for each state-changing phase:

  * anonymous probe,
  * primary login result,
  * MFA challenge evidence,
  * pending-MFA protected probe,
  * verified-MFA baseline when available.
* Store only short response excerpts needed for proof.
* Redact cookies, authorization headers, CSRF tokens, MFA secrets, recovery codes, and personal data.
* Store response fingerprints instead of full bodies when possible.
* Link every finding to the exact evidence IDs that prove the decision.
* Do not persist raw credentials, MFA codes, or session cookies.

## Safety

This check is safe only when it uses operator-provided accounts and bounded HTTP probes.

Default behavior:

* Read-only.
* `GET`, `HEAD`, and `OPTIONS` only.
* No MFA-code guessing.
* No brute force.
* No credential stuffing.
* No real user accounts.
* No push notifications.
* No recovery-code attempts.
* No phishing or out-of-band interaction.
* No bypass attempts against third-party identity providers unless the target scope explicitly includes them.

`POST` is allowed only when all of these are true:

* The target is a local fixture or explicitly configured safe test environment.
* The action is marked `fixture_safe`.
* The request is idempotent or reset by the fixture harness.
* The action cannot notify real users, change billing, change credentials, create tokens, delete data, or expose secrets.

Payload restrictions:

* Use only fixture-provided benign values.
* Do not submit passwords, email changes, API-key creation, recovery-code generation, or destructive account changes on real targets.
* Do not tamper with signed cookies or JWTs unless the target is a local fixture created for this test. Token tampering belongs in a separate signed-token/authz spec.

PII handling:

* Redact email addresses unless they are fixture accounts.
* Redact names, account IDs, phone numbers, tokens, and cookies.
* Store only the smallest body excerpt needed to prove the authorization decision.

AI involvement: `None`.

A deterministic gap may be recorded when the scanner cannot know which routes require MFA without operator-provided route metadata or a verified-MFA baseline. In that case, the runner may mark the result as `candidate` with `confidence=low | medium`, but it must not ask AI to decide whether a route is protected.

## Pass/fail check

The implementation passes when all assertions below are true.

Positive assertions:

* Given valid test credentials for an MFA-enabled account, the runner can reach and record `primary_authenticated_mfa_pending` without completing MFA.
* Anonymous probe evidence is stored before pending-MFA probe evidence.
* Pending-MFA probe evidence stores status, redirect target, response fingerprint, and matched indicators.
* A route returning `401`, `403`, login redirect, MFA redirect, or `mfa_required` is classified as blocked or MFA-required.
* A configured protected route returning successful protected content before MFA completion creates a finding.
* A finding is `confirmed` only when protected access is proven by fixture metadata, configured route metadata, or verified-MFA baseline.
* `confidence=high` requires stronger evidence than a simple `2xx`.
* The final finding includes `Evidence` IDs for the anonymous and pending-MFA probes.
* The scanner handles CSRF failures as inconclusive unless the authorization decision is still clear.
* Session state is isolated between anonymous, pending-MFA, and verified-MFA clients.

Negative assertions:

* The runner must not submit guessed MFA codes.
* The runner must not retry many MFA variants.
* The runner must not use leaked recovery codes.
* The runner must not test real user accounts.
* The runner must not call external URLs found in response bodies.
* The runner must not perform destructive actions.
* The runner must not classify client-side route rendering alone as confirmed bypass.
* The runner must not persist credentials, cookies, bearer tokens, CSRF tokens, MFA secrets, or recovery codes.
* The runner must not hard-code hostname, framework, product, or expected technology.
* The runner must not mark a finding as confirmed when the route is not known or shown to be MFA-protected.
* The runner must not use AI to decide exploitability, severity, or route sensitivity.
* The runner must not continue beyond `max_requests`.

Fixture assertions:

* A vulnerable fixture route that allows access before MFA produces `status=confirmed`.
* A fixed fixture route that redirects pending-MFA users to MFA produces `status=rejected`.
* A route that is public for anonymous users does not produce a finding.
* A route blocked by CSRF but not proven accessible before MFA produces no confirmed finding.

## Test fixtures

Preferred fixture: `webgoat` if an MFA bypass lesson or test harness exists in the project.

Fallback fixture: create a small local fixture named `mfa-bypass-fixture`.

The fixture should expose:

* `POST /login`

  * Accepts fixture credentials.
  * Creates a session with `primary_authenticated=true` and `mfa_verified=false`.
  * Redirects to `/mfa`.

* `GET /mfa`

  * Shows a deterministic MFA challenge page.
  * No real MFA provider.
  * No outbound messages.

* `POST /fixture/complete-mfa`

  * Test-only endpoint.
  * Marks the fixture session as `mfa_verified=true`.
  * Enabled only in fixture mode.

* `GET /account`

  * Safe authenticated route.
  * May be visible before MFA if the fixture needs a limited dashboard.

* `GET /security`

  * Protected route.
  * Vulnerable mode: returns security settings with `mfa_verified=false`.
  * Fixed mode: returns `403` or redirects to `/mfa`.

* `GET /api/recovery-codes`

  * Protected route.
  * Vulnerable mode: returns fake fixture-only recovery-code metadata, not real codes.
  * Fixed mode: returns `mfa_required`.

* `POST /api/profile/display-name`

  * Optional fixture-safe action.
  * Uses benign values only.
  * Vulnerable mode: accepts before MFA.
  * Fixed mode: returns `mfa_required`.

Fixture data:

* `alice@example.test` with password `CorrectHorseFixture1!`, MFA enabled.
* Fake recovery-code metadata only, never real reusable recovery codes.
* Reset script clears sessions and profile changes between tests.

The fixture must support both modes:

* `MFA_BYPASS_MODE=vulnerable`
* `MFA_BYPASS_MODE=fixed`

## Acceptance criteria

The implementation is acceptable when:

* It uses shared `ScanTarget` and `Evidence`.
* It defines only `MfaBypassSignature` and `MfaBypassFinding` as stub-specific persistence types.
* It completes within the configured request budget.
* It uses isolated HTTP clients for anonymous, pending-MFA, and verified-MFA states.
* It records enough evidence to explain the decision without storing secrets.
* It redacts credentials, cookies, tokens, CSRF values, MFA secrets, recovery codes, and personal data.
* It handles TLS errors, timeouts, redirect loops, missing login paths, and missing credentials gracefully.
* It reports `rejected` or no finding when MFA enforcement works.
* It reports `candidate` rather than `confirmed` when route sensitivity is uncertain.
* It reports `confirmed` only when protected access before MFA is proven.
* It is idempotent against the fixture.
* It does not perform unsafe mutation outside fixture mode.
* It does not call real MFA providers or send real MFA challenges.
* It does not brute force, guess, intercept, or reuse MFA codes.
* It does not rely on hostname-specific assumptions.
* It does not use AI.
* It has unit tests for state tracking, decision classification, redaction, request budgeting, and evidence linking.
* It has integration tests against vulnerable and fixed fixture modes.

