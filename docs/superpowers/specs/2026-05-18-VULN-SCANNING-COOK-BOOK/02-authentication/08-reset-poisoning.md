---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 8
slug: reset-poisoning
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.8 Reset poisoning

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

Detect password-reset flows that build reset links from attacker-controlled request metadata, such as `Host`, `X-Forwarded-Host`, `X-Forwarded-Proto`, or `Forwarded`. A runner cares because a poisoned reset email can send a valid reset token to an attacker-controlled origin, even when the token itself is strong and single-use.

## Inputs

The runner receives a shared `ScanTarget` plus optional reset-flow configuration.

Required input:

* `target`: shared `ScanTarget`.
* `run_id`: stable scanner run identifier used for evidence correlation.

Optional input:

* `canonical_origin`: expected public origin for reset links. If omitted, derive from `ScanTarget.url`.
* `reset_paths`: candidate paths to probe before discovery fallback.
* `test_email`: owned test account email. Required for active reset submission.
* `test_username`: optional username if the reset form needs a username instead of email.
* `mailbox_adapter`: controlled mailbox or mail-sink adapter, such as MailHog, Mailpit, MailSlurper, or fixture-local API.
* `mailbox_timeout_ms`: default `10000`.
* `max_reset_submissions`: default `4`, hard cap `6`.
* `request_timeout_ms`: default from shared scanner settings.
* `canary_host_suffix`: default `scanner.invalid`; may be replaced by a scanner-controlled sink domain.
* `allow_mutating_reset_request`: default `false`.
* `allowed_header_tests`: default:

  * `host`
  * `x-forwarded-host`
  * `x-forwarded-proto`
  * `forwarded-host`
  * `forwarded-proto`

Active detection requires all of these:

* `allow_mutating_reset_request=true`
* owned `test_email` or owned `test_username`
* a configured `mailbox_adapter`
* target in an allowed scan scope

If those are missing, the runner may still perform passive discovery and mark any result as `candidate`, not `confirmed`.

## Detection logic

Detection is deterministic and evidence-based.

### 1. Discover password-reset endpoint

Use safe GET requests first.

Candidate paths:

* `/forgot-password`
* `/forgot`
* `/password-reset`
* `/reset-password`
* `/users/password/new`
* `/account/forgot-password`
* `/auth/forgot-password`
* `/auth/reset`
* `/login`
* `/signin`

For each response:

* Store response status, URL, selected headers, and a minimized body excerpt as shared `Evidence`.
* Parse HTML forms.
* Prefer forms containing password-reset intent:

  * link text or form text contains `forgot`, `reset`, `password`, `recover`, or `account recovery`
  * input names include `email`, `username`, `user`, `login`, or `account`
  * action path contains `forgot`, `reset`, `recover`, or `password`
* Preserve CSRF and hidden fields for the active request.
* Resolve relative form actions against the response URL.
* Do not submit login forms unless reset intent is explicit.

If no form is found, return no finding unless passive evidence shows a reset URL builder or reflected authority signal.

### 2. Establish baseline reset email

Only run this step when active detection is enabled.

Submit one baseline reset request using normal target authority.

Rules:

* Use the owned test identity only.
* Send the minimum form fields needed.
* Include CSRF and hidden fields discovered from the form.
* Do not follow reset links.
* Do not redeem, validate, or brute force tokens.
* Do not submit against real user accounts.

After submission:

* Poll the controlled mailbox.
* Extract reset URLs from the newest matching message.
* Match messages by recipient, timestamp, and reset-related subject/body.
* Store the email metadata and extracted URLs as shared `Evidence`.
* Redact token query values in logs and display output.
* Keep the full raw message only in the secure evidence store if the project already supports one.

The baseline is valid when at least one reset URL points to `canonical_origin`.

If no baseline email arrives, skip active poisoning checks and return `rejected` or `candidate` depending on passive evidence.

### 3. Submit controlled poison probes

For each enabled header test, submit one reset request with one poison signal at a time.

Use a unique canary authority per probe:

```text
reset-poison-<run_id>-<probe_name>.<canary_host_suffix>
```

Example probe matrix:

| Probe name          | Request mutation                                                                                  | Expected safe behavior                    |
| ------------------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `host`              | poisoned `Host` authority, only when the HTTP client supports controlled authority testing safely | reset email still uses `canonical_origin` |
| `x_forwarded_host`  | `X-Forwarded-Host: <canary>`                                                                      | reset email still uses `canonical_origin` |
| `x_forwarded_proto` | `X-Forwarded-Proto: http`                                                                         | reset email still uses canonical scheme   |
| `forwarded_host`    | `Forwarded: host=<canary>`                                                                        | reset email still uses `canonical_origin` |
| `forwarded_proto`   | `Forwarded: proto=http`                                                                           | reset email still uses canonical scheme   |

HTTP client rules:

* Keep TLS verification enabled unless shared scanner config explicitly allows insecure TLS.
* Do not spoof source IP headers.
* Do not include `X-Forwarded-For` for this stub.
* Do not combine multiple poison headers in one probe.
* Do not use external callback URLs.
* Do not make requests to the canary host.
* Do not click links in emails.
* Do not retry a mutating request unless transport failed before the request was sent.

After each probe:

* Poll the controlled mailbox for the matching reset email.
* Extract reset URLs.
* Compare each reset URL against:

  * `canonical_origin`
  * submitted canary host
  * submitted scheme mutation
* Store request, response, email metadata, and extracted URL evidence.

### 4. Classify result

Create a finding only when there is deterministic evidence.

Confirmed finding:

* A reset email for the owned test account contains a reset URL whose authority or scheme was influenced by a submitted poison signal.
* The evidence links the submitted request to the received email.
* The affected URL contains a reset token or reset path.

Candidate finding:

* Passive evidence strongly suggests reset-link construction from request authority, but no controlled mailbox is available.
* The reset response reflects a poisoned host in reset-related content, but no reset email can be inspected.
* The app returns a reset preview URL containing the poisoned authority in a non-production fixture.

Rejected finding:

* Baseline reset works.
* Poison probes do not affect reset URL authority or scheme.
* No reset endpoint is found.
* Active checks are not enabled and passive evidence is absent.

Stale finding:

* Previous evidence exists, but the current scan cannot reproduce it and the target or reset flow has changed.

Confidence:

* `high`: controlled reset email contains a poisoned reset link matching a submitted canary.
* `medium`: controlled reset response or fixture preview contains a poisoned reset link, but no email was inspected.
* `low`: passive evidence only, such as reflected authority in reset-related response content.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only the stub-specific types below.

```ts
export type ResetPoisoningProbeKind =
  | "host"
  | "x_forwarded_host"
  | "x_forwarded_proto"
  | "forwarded_host"
  | "forwarded_proto"
  | "passive_reflection";

export type ResetPoisoningSignature = {
  id: string;
  probe_kind: ResetPoisoningProbeKind;
  reset_endpoint_url: string;
  form_method: "GET" | "POST";
  injected_authority?: string;
  injected_scheme?: "http" | "https";
  observed_reset_url?: string;
  observed_reset_origin?: string;
  expected_reset_origin: string;
  token_redacted: boolean;
  matched_email: boolean;
  evidence_ids: string[];
};

export type ResetPoisoningFinding = {
  id: string;
  target: ScanTarget;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  title: string;
  summary: string;
  signatures: ResetPoisoningSignature[];
  evidence: Evidence[];
  affected_endpoint?: string;
  affected_header?: ResetPoisoningProbeKind;
  expected_origin: string;
  observed_origin?: string;
  impact: string;
  remediation: string;
  created_at: string;
  updated_at: string;
};
```

Persistence rules:

* Store one finding per affected reset endpoint.
* Store one signature per poison signal that influenced a reset link.
* Redact reset tokens in persisted summaries and non-secure logs.
* Keep evidence IDs stable.
* Link every finding to the request evidence and email evidence that prove the result.
* Do not persist raw mailbox contents outside the shared evidence mechanism.
* Do not store credentials, cookies, or reset tokens in the finding body.

## Safety

This stub can be mutating because password-reset submission may create emails and reset tokens. Active probing is disabled by default.

Allowed without explicit active permission:

* GET reset-discovery paths.
* Parse forms.
* Inspect headers and response bodies.
* Record passive evidence.

Allowed only when `allow_mutating_reset_request=true`:

* Submit reset request for an owned test account.
* Poll a controlled mailbox or fixture-local mail sink.
* Extract reset URLs from the controlled mailbox.

Never allowed:

* Testing against real user accounts.
* Using leaked emails or guessed usernames.
* Brute forcing reset tokens.
* Redeeming reset tokens.
* Clicking reset links.
* Sending reset emails to third parties.
* Using external callback infrastructure unless it is explicitly scanner-owned.
* Combining this check with account takeover verification.
* Reusing reset tokens across probes.
* Disabling TLS verification unless shared scanner config allows it.

Payload restrictions:

* Canary host must be synthetic and unique per probe.
* Default canary suffix must be `.invalid` or a scanner-owned sink domain.
* Header values must be plain host/scheme values, not scripts, shell syntax, CRLF payloads, or encoded bypass strings.
* Do not inject path traversal, SSRF URLs, credentials, or userinfo into the authority.

PII handling:

* Use only the configured owned test identity.
* Redact email local-part in user-facing output unless the project already treats test identities as non-sensitive.
* Redact reset tokens from URLs before logging or reporting.
* Store only message metadata, matching reason, and minimized reset-link evidence by default.

AI involvement: `None`.

Deterministic gap:

* If no controlled mailbox or fixture-local email sink is available, the runner cannot confirm reset poisoning. It must report only passive `candidate` evidence or `rejected`, and must not ask AI to infer exploitability.

## Pass/fail check

The implementation passes when these assertions hold.

Discovery assertions:

* Given a page with an explicit password-reset form, the runner identifies the reset endpoint.
* Given a login form without reset intent, the runner does not submit it.
* Given relative form actions, the runner resolves them against the response URL.
* Given CSRF hidden fields, the runner preserves them in the active request.

Baseline assertions:

* Given active mode, an owned test account, and a working mail sink, the runner sends one baseline reset request.
* The runner extracts reset URLs from the matching test-account email.
* The runner redacts token values before logs or findings.
* If no baseline email arrives, the runner does not continue with poison probes.

Poison detection assertions:

* If `X-Forwarded-Host: canary.invalid` causes the reset email link to use `canary.invalid`, the finding status is `confirmed`.
* If `Forwarded: host=canary.invalid` causes the reset email link to use `canary.invalid`, the finding status is `confirmed`.
* If `X-Forwarded-Proto: http` causes the reset email link to downgrade from `https` to `http`, the finding status is `confirmed`.
* If all reset emails use the canonical origin, the finding status is `rejected`.
* If only passive reflection exists and no mailbox is available, the finding status is `candidate`, not `confirmed`.

Negative assertions:

* The runner must not submit reset requests unless `allow_mutating_reset_request=true`.
* The runner must not test real user accounts.
* The runner must not click, redeem, or validate reset tokens.
* The runner must not brute force tokens.
* The runner must not send more than `max_reset_submissions`.
* The runner must not combine multiple poison headers in one request.
* The runner must not use `X-Forwarded-For`.
* The runner must not log full reset URLs with live token values.
* The runner must not hard-code framework or technology expectations from hostname.
* The runner must not mark a finding `confirmed` without email or fixture evidence showing a poisoned reset link.
* The runner must not call AI to decide whether the target is vulnerable.

Example unit test names:

```text
test_discovers_explicit_password_reset_form
test_does_not_submit_plain_login_form
test_preserves_csrf_fields_for_reset_submission
test_active_mode_requires_owned_identity_and_mailbox
test_baseline_email_must_arrive_before_poison_probes
test_x_forwarded_host_poisoned_link_is_confirmed
test_forwarded_host_poisoned_link_is_confirmed
test_x_forwarded_proto_scheme_downgrade_is_confirmed
test_canonical_links_reject_finding
test_passive_reflection_without_mailbox_is_candidate
test_tokens_are_redacted_from_logs_and_findings
test_never_clicks_or_redeems_reset_links
test_enforces_max_reset_submissions
test_does_not_combine_poison_headers
```

## Test fixtures

Preferred fixture: new `reset-poisoning` fixture.

The fixture should expose:

* A password-reset page with a form accepting an owned test email.
* A local mail sink API.
* A safe vulnerable mode that builds the reset URL from request authority headers.
* A safe fixed mode that always uses configured canonical origin.
* A reset token format that is clearly fake and non-sensitive.
* A mailbox cleanup endpoint for test isolation.

Suggested fixture behavior:

| Mode                           | Behavior                                                 |
| ------------------------------ | -------------------------------------------------------- |
| `vulnerable_x_forwarded_host`  | reset email link host comes from `X-Forwarded-Host`      |
| `vulnerable_forwarded_host`    | reset email link host comes from `Forwarded: host=`      |
| `vulnerable_x_forwarded_proto` | reset email link scheme comes from `X-Forwarded-Proto`   |
| `fixed_canonical_origin`       | reset email link always uses configured canonical origin |
| `no_mail_sent`                 | reset request accepted but no email appears              |
| `login_only`                   | login form exists but reset form is absent               |

Fixture assertions:

* The vulnerable modes produce deterministic poisoned links.
* The fixed mode never uses poison headers in reset links.
* The mail sink exposes message metadata and body for the owned test account only.
* The fixture does not send external email.
* Tokens are fake and cannot affect real accounts.

Fallback fixtures:

* `juice-shop`: may be used only if a local mail-capture setup and owned test account are available. Otherwise use it for passive reset-form discovery only.
* `dvwa`: not preferred unless a fixture extension adds a reset-email flow.
* `webgoat`: not preferred unless a fixture extension adds a reset-email flow.

## Acceptance criteria

Implementation is accepted when:

* The runner is idempotent for passive discovery.
* Active mode is opt-in and requires an owned test identity plus controlled mailbox.
* The runner completes within the shared phase budget.
* The runner enforces `max_reset_submissions`.
* Each mutating probe is sent at most once unless the request failed before transmission.
* TLS errors are handled through shared scanner error handling and do not crash the run.
* Network timeouts produce a clean rejected or incomplete result with evidence.
* The runner stores request, response, and mailbox evidence with stable IDs.
* Reset tokens are redacted in logs, findings, and snapshots.
* Confirmed findings require deterministic poisoned-link evidence.
* Candidate findings are clearly separated from confirmed findings.
* The check works against vulnerable and fixed fixture modes.
* Tests cover discovery, baseline, each poison header, safety gates, redaction, and negative assertions.
* No AI is used for detection, classification, severity, or remediation.
* The implementation follows shared coding-agent rules from `../00-shared-schema.md`.

