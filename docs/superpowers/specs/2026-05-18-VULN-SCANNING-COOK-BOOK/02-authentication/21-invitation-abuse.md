---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 21
slug: invitation-abuse
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.21 Invitation abuse

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

Detect invitation flows that let an unauthorized or wrongly scoped user join an account, tenant, team, workspace, project, or privileged role. A runner cares because invitation bugs often sit between registration, authorization, and tenant isolation: an invite may be reusable, unbound to the intended recipient, accepted after expiry, accepted by the wrong account, or used to gain a stronger role than the inviter intended.

## Inputs

The runner receives the shared `ScanTarget` plus optional scan settings.

Required:

* `target`: shared `ScanTarget`.
* `evidence`: shared `Evidence[]` gathered during discovery, login, registration, or invite-flow crawling.

Optional credentials and actors:

* `inviter_session`: authenticated session for a low-privileged account that is allowed to view or create invitations in the test environment.
* `recipient_session`: authenticated session for a second owned test account.
* `unrelated_session`: authenticated session for a third owned test account in a different tenant or workspace.
* `anonymous_session`: unauthenticated client used only for GET/HEAD/OPTIONS and safe form inspection.
* `mailbox_probe`: controlled email sink or test inbox for receiving invite links, if the environment supports it.

Config knobs:

* `max_invite_create_attempts`: default `0`; must be explicitly raised to allow invite creation.
* `allow_mutating_invite_probe`: default `false`.
* `allowed_invite_domains`: list of domains the runner may use for test recipients.
* `test_recipient_email`: controlled recipient address. Must not be a real customer/user address.
* `test_unrelated_email`: controlled address for wrong-recipient checks.
* `max_accept_attempts_per_invite`: default `1`.
* `max_candidate_invite_endpoints`: default `20`.
* `max_response_body_bytes`: default from shared scanner limits.
* `follow_redirects`: default `false` for state-changing requests, `true` for read-only discovery.
* `timeout_seconds`: per request timeout.
* `tls_policy`: shared TLS handling policy.
* `respect_robots`: project default for passive crawling.
* `scan_mode`: `passive | authenticated-readonly | controlled-mutating`.

Inputs the runner must not require:

* Real user accounts.
* Leaked invitation tokens.
* Brute-forced token guesses.
* Access to production mailboxes.
* Knowledge of expected technology by hostname.

## Detection logic

Detection is deterministic and evidence based. The runner must not guess expected behavior from a hostname, framework, product name, or visual theme.

### 1. Find invitation surfaces

Use existing crawler evidence and safe requests to identify invite-related surfaces.

Candidate paths, links, forms, API routes, route names, JavaScript strings, and response text may include:

* `invite`
* `invitation`
* `invitations`
* `join`
* `accept`
* `team`
* `workspace`
* `organization`
* `tenant`
* `members`
* `collaborators`
* `guests`
* `role`
* `pending_members`

Discovery methods:

* Inspect HTML links and forms from existing evidence.
* Inspect same-origin JavaScript route strings already fetched by the crawler.
* Inspect `sitemap.xml`, if already in scope.
* Use `GET`, `HEAD`, or `OPTIONS` against candidate endpoints only when allowed by shared crawler policy.
* Do not submit forms during discovery.
* Do not create accounts or invitations during passive discovery.

Classify a candidate surface as invite-related when response evidence contains at least one structural signal and one semantic signal.

Structural signals:

* Form action or API route contains an invite term.
* JSON field name contains an invite term.
* Link path contains an invite term.
* Button text or form label refers to inviting, joining, accepting, members, guests, workspace, team, organization, or tenant.
* Response sets or reads a token-like invite parameter.

Semantic signals:

* Text says an invitation can be accepted.
* Text asks for an email address to invite a member.
* Text references pending invitations.
* Text references role selection for invitees.
* Text references joining a workspace, team, organization, project, tenant, or account.

Record these as `InvitationAbuseSignature` objects with confidence `low` or `medium`. Do not create a confirmed finding from surface discovery alone.

### 2. Parse invitation token handling from evidence

For discovered invitation links and forms, deterministically extract only token metadata. Do not attempt to guess or brute force tokens.

Recognized token locations:

* Query parameters such as `token`, `invite`, `invitation`, `code`, `key`, `t`, `invitation_token`.
* Path segments after invite-like routes.
* Hidden form inputs.
* JSON fields returned by owned test actions.
* Email link URLs from a controlled mailbox probe.

For each token-bearing link, record:

* token location
* token length
* token character class
* whether the token appears opaque or structured
* whether the link contains recipient binding hints, such as email hash, recipient ID, organization ID, tenant ID, or role
* whether the response displays target tenant/workspace/role before authentication
* whether the response exposes inviter or recipient PII

Token quality alone is not enough to confirm invitation abuse unless the application also accepts or appears to accept a dangerous flow. Short or structured tokens are `candidate` findings unless validated by a safe controlled flow.

### 3. Passive vulnerability indicators

The runner may create candidate findings without mutation when evidence shows a likely unsafe state.

Candidate indicators:

* Public invite acceptance page displays tenant, workspace, role, or inviter details before authentication.
* Invite acceptance page allows arbitrary email entry while the invite link appears intended for a specific recipient.
* Invitation creation UI allows selecting privileged roles from a low-privileged session.
* Invitation UI exposes reusable invite links for broad roles without expiry text, recipient binding, or revocation controls.
* API schema or page text states that “anyone with the link can join” for a non-public tenant, team, or workspace.
* Invite acceptance route returns success-like content to an anonymous GET request.
* Pending invitations are visible to a user who is not an owner/admin.
* Invite link appears to cross tenant/workspace boundaries in URL or response metadata.

These remain `candidate` unless a controlled probe confirms acceptance, role escalation, wrong-recipient acceptance, reuse, or missing expiry.

### 4. Controlled invite creation probe

Only run this phase when all are true:

* `scan_mode` is `controlled-mutating`.
* `allow_mutating_invite_probe` is `true`.
* `max_invite_create_attempts > 0`.
* `inviter_session` is present.
* `test_recipient_email` is present and belongs to `allowed_invite_domains`.
* The target is an approved test or staging target under the shared scope rules.

The runner may submit one invitation request using the lowest available role unless a specific lower-privileged role is required by the fixture.

Before submitting, extract the invitation form or API contract from evidence:

* HTTP method
* action URL
* CSRF field, if present
* email field
* role field, if present
* tenant/workspace/project field, if present

Rules:

* Use only controlled recipient addresses.
* Do not invite real users.
* Do not invite external domains unless explicitly allowed.
* Do not retry with many role values.
* Do not bypass CSRF.
* Do not use guessed endpoint names for mutating requests.
* Do not send more than `max_invite_create_attempts`.

Record the request and response as evidence with sensitive values redacted.

### 5. Controlled acceptance probes

Only run this phase for an invite created by the scanner or supplied through controlled test evidence.

Probe types:

1. Intended recipient acceptance

   * Open the invite link with `recipient_session` or anonymous session, depending on the flow.
   * Stop before final acceptance unless `allow_mutating_invite_probe` permits acceptance.
   * If acceptance is allowed, accept once and record whether the recipient joined the expected tenant/workspace with the expected role.

2. Wrong-recipient acceptance

   * Use `unrelated_session` or `test_unrelated_email`.
   * Attempt to open the invite link.
   * A safe result is rejection, login prompt bound to intended recipient, or error without membership change.
   * A finding is confirmed if the unrelated owned account can accept the invite or is added to the tenant/workspace.

3. Reuse check

   * After intended acceptance, attempt to reuse the same invite link once with the same session or unrelated session.
   * A safe result is expired, already used, revoked, or rejected.
   * A finding is confirmed if the same single-use invite can add another account or create another membership.

4. Role escalation check

   * Compare requested role in the invite request with effective role after acceptance, using response evidence or accessible profile/member endpoint.
   * A finding is confirmed if the accepted user receives a stronger role than requested or a low-privileged inviter can grant a privileged role without authorization evidence.

5. Tenant binding check

   * Compare tenant/workspace/project identifiers from the invite creation context, invite preview, acceptance response, and post-accept membership evidence.
   * A finding is confirmed if the invite can be accepted into a different tenant/workspace/project than the one that created it.

Do not perform expiry testing by waiting long periods or repeatedly probing the same token. Expiry absence may be a candidate from UI/API evidence; confirmed expiry abuse requires fixture-controlled evidence.

### 6. Finding confidence

Use deterministic confidence levels:

* `high`: controlled probe confirms unauthorized acceptance, wrong-recipient acceptance, invite reuse, tenant crossing, or role escalation.
* `medium`: authenticated evidence strongly shows an unsafe invite design, but no final acceptance was performed.
* `low`: passive evidence suggests an invite flow or missing control, but behavior is not confirmed.

Use status as follows:

* `candidate`: evidence suggests possible invitation abuse.
* `confirmed`: controlled evidence proves abuse within scope.
* `rejected`: a safe control was observed, such as recipient binding, single-use rejection, or role enforcement.
* `stale`: previously observed invite behavior no longer reproduces or evidence is too old under shared freshness rules.

## Persistence

Use the shared `ScanTarget` and `Evidence` types from `../00-shared-schema.md`. Do not redefine them here.

Define only these stub-specific types:

```ts
export type InvitationAbuseProbeType =
  | "surface_discovery"
  | "token_metadata"
  | "invite_creation"
  | "intended_recipient_acceptance"
  | "wrong_recipient_acceptance"
  | "reuse_check"
  | "role_escalation_check"
  | "tenant_binding_check"
  | "expiry_indicator";

export type InvitationAbuseWeakness =
  | "public_invite_surface"
  | "invite_token_exposed"
  | "recipient_not_bound"
  | "invite_reusable"
  | "invite_not_expiring"
  | "role_escalation"
  | "tenant_not_bound"
  | "unauthorized_invite_creation"
  | "sensitive_invite_preview"
  | "pending_invites_exposed";

export interface InvitationAbuseSignature {
  id: string;
  target_id: string;
  evidence_ids: string[];
  probe_type: InvitationAbuseProbeType;
  endpoint_url: string;
  http_method: "GET" | "HEAD" | "OPTIONS" | "POST" | "PUT" | "PATCH";
  weakness: InvitationAbuseWeakness;
  observed_result: string;
  expected_safe_result?: string;
  token_location?: "query" | "path" | "hidden_form" | "json" | "email_link";
  token_length?: number;
  token_shape?: "opaque" | "structured" | "short" | "unknown";
  intended_recipient_hint_present?: boolean;
  tenant_hint_present?: boolean;
  role_hint_present?: boolean;
  inviter_role?: string;
  requested_invitee_role?: string;
  observed_invitee_role?: string;
  intended_tenant_hint?: string;
  observed_tenant_hint?: string;
  mutation_performed: boolean;
  confidence: "low" | "medium" | "high";
  created_at: string;
}

export interface InvitationAbuseFinding {
  id: string;
  target_id: string;
  signature_ids: string[];
  evidence_ids: string[];
  title: string;
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  weakness: InvitationAbuseWeakness;
  affected_endpoint_url: string;
  affected_scope?: "account" | "tenant" | "organization" | "workspace" | "team" | "project" | "unknown";
  impact_summary: string;
  reproduction_summary: string;
  safe_expected_behavior: string;
  mutation_performed: boolean;
  pii_redacted: boolean;
  remediation: string;
  created_at: string;
  updated_at: string;
}
```

Persistence rules:

* Store each HTTP request/response used for the finding as shared `Evidence`.
* Redact invite tokens in display fields. Keep full tokens only if the shared secure evidence store already supports secret handling.
* Redact email addresses except controlled test domains where project policy allows full storage.
* Link findings to signature IDs and evidence IDs.
* Store role and tenant identifiers only when observed in response evidence.
* Do not store guessed tenant names, product names, or roles.
* Mark any finding created from passive evidence as `candidate`.
* Mark confirmed findings only when controlled evidence proves the unsafe behavior.

## Safety

Default behavior is read-only.

Safe by default:

* `GET`, `HEAD`, and `OPTIONS` for discovery.
* Parsing already collected HTML, JavaScript, JSON, headers, and email fixture evidence.
* Inspecting invite forms without submitting them.
* Extracting token metadata without testing guessed tokens.

Mutating behavior is disabled unless explicitly configured:

* Creating an invite is mutating.
* Accepting an invite is mutating.
* Reusing an invite after acceptance is mutating.
* Changing a role, tenant, workspace, or membership is mutating.
* Sending invitation email is mutating.

Mutating probes are allowed only in controlled test scopes with owned test accounts and controlled mailbox addresses.

Payload restrictions:

* Do not brute force invite tokens.
* Do not enumerate invitation IDs.
* Do not test leaked or third-party invite links.
* Do not invite real users.
* Do not use customer or employee email addresses.
* Do not send many invitation variants.
* Do not bypass CSRF or authentication controls.
* Do not attempt privilege escalation outside the owned test actor set.
* Do not continue probing after successful confirmation.
* Do not perform destructive cleanup unless the shared framework already has an approved cleanup step.

PII handling:

* Treat invite tokens as secrets.
* Treat email addresses, inviter names, workspace names, and tenant names as sensitive.
* Redact tokens and non-test email addresses in logs and findings.
* Keep raw evidence only in the shared secure evidence store, if available.

AI involvement: `None`.

Deterministic gap:

* AI must not decide whether an invitation is vulnerable.
* AI may later summarize a confirmed finding for a report only from persisted `InvitationAbuseFinding` and shared evidence IDs.
* AI must not receive raw invite tokens or full email addresses unless the shared evidence minimization layer redacts them first.

## Pass/fail check

A coding agent implementation passes when the following assertions are true.

Discovery assertions:

* The runner identifies invite-related links, forms, and API routes from response evidence.
* The runner records `InvitationAbuseSignature` objects for invite surfaces.
* The runner does not create a confirmed finding from surface discovery alone.
* The runner does not hard-code hostname, vendor, framework, or expected technology.
* The runner does not submit invitation forms during passive discovery.

Token handling assertions:

* The runner extracts token location, length, and shape from owned or discovered invite links.
* The runner redacts invite tokens in logs and finding text.
* The runner does not brute force, mutate, increment, decode as authority, or guess invite tokens.
* The runner does not mark a short token as confirmed abuse without acceptance or authorization evidence.

Controlled mutation assertions:

* With `allow_mutating_invite_probe=false`, the runner performs no invite creation, acceptance, reuse, role-change, or membership-changing requests.
* With `scan_mode=passive`, the runner performs no mutating requests.
* With controlled mutation enabled, the runner uses only configured owned test email addresses.
* The runner sends no more than `max_invite_create_attempts`.
* The runner performs no more than `max_accept_attempts_per_invite`.
* The runner stops after confirming the first unsafe behavior for a given invite token.

Recipient-binding assertions:

* A wrong-recipient acceptance attempt that succeeds creates a `confirmed` finding with confidence `high`.
* A wrong-recipient acceptance attempt that is rejected records a `rejected` signature or no finding.
* The runner must not treat a login prompt alone as a vulnerability.

Reuse assertions:

* A reused invite that adds another owned test account creates a `confirmed` finding with confidence `high`.
* A reused invite that returns expired, already-used, revoked, or rejected must not create a confirmed finding.

Role assertions:

* If a low-privileged inviter can grant a privileged role, the runner creates a `confirmed` finding.
* If the accepted role is stronger than the requested role, the runner creates a `confirmed` finding.
* If role names are not observable, the runner must not invent them.

Tenant-binding assertions:

* If an invite can be accepted into a tenant/workspace/project different from the creator context, the runner creates a `confirmed` finding.
* If tenant or workspace identifiers are not observable, the runner records `unknown` rather than guessing.

Negative assertions:

* The runner must not invite real users.
* The runner must not send invitations to domains outside `allowed_invite_domains`.
* The runner must not use leaked invite links.
* The runner must not brute force invite tokens.
* The runner must not perform repeated expiry polling.
* The runner must not follow off-scope invite URLs.
* The runner must not store raw invite tokens in normal logs.
* The runner must not call AI for detection.
* The runner must not persist `confirmed` without evidence IDs.
* The runner must not downgrade a confirmed finding to rejected unless fresh evidence proves the control now works.

## Test fixtures

Preferred fixture: `webgoat`.

Use or add a training fixture named `invitation-abuse` if the current container does not expose a suitable invite flow.

Fixture requirements:

* Provides an authenticated inviter account.
* Provides an intended recipient test account.
* Provides an unrelated owned test account.
* Exposes an invite creation endpoint.
* Emits an invite link through a controlled test mailbox, fixture API, or deterministic fixture response.
* Allows a vulnerable mode and a safe mode.

Vulnerable fixture behaviors:

* Invite token is not bound to the intended recipient.
* Same invite token can be reused by a second owned account.
* Low-privileged inviter can request or cause a privileged role.
* Invite preview leaks tenant/workspace and role before authentication.
* Invite acceptance can add an unrelated account to the tenant/workspace.

Safe fixture behaviors:

* Invite token is single-use.
* Invite token is bound to intended recipient or verified email.
* Invite acceptance requires authentication as the intended recipient.
* Role is enforced server-side.
* Tenant/workspace binding is enforced server-side.
* Expired or revoked invites are rejected.

If `webgoat` is not practical, add a small local fixture app under a new slug:

* `invitation-abuse`

Minimum fixture endpoints:

* `POST /fixture/invitations`
* `GET /fixture/invitations/:token`
* `POST /fixture/invitations/:token/accept`
* `GET /fixture/members`
* `POST /fixture/reset`

The fixture must support deterministic setup and teardown so the scanner can run repeatedly without flakiness.

## Acceptance criteria

Implementation quality bar:

* Uses shared `ScanTarget` and `Evidence` only; does not redefine them.
* Defines only `InvitationAbuseSignature` and `InvitationAbuseFinding` plus local enums.
* Runs safely in passive mode without mutation.
* Requires explicit opt-in for invite creation and acceptance.
* Uses only owned test accounts and controlled email domains.
* Completes within the shared scan budget.
* Handles TLS errors according to shared scanner policy.
* Handles redirects without following off-scope invite URLs.
* Handles missing credentials by producing only passive candidate signatures.
* Handles absent invite surfaces without creating findings.
* Handles CSRF-protected forms without bypass attempts.
* Handles JSON, HTML, and redirect-based invite flows.
* Redacts invite tokens and non-test PII from logs and finding text.
* Produces deterministic confidence and status values.
* Produces stable evidence IDs and links all findings to evidence.
* Has unit tests for parsing, passive indicators, mutation gating, token redaction, recipient binding, reuse, role escalation, tenant binding, and negative assertions.
* Has integration tests against the selected fixture in vulnerable and safe modes.
* Does not call external email systems unless a controlled mailbox probe is explicitly configured.
* Does not use AI for detection.
* Does not retry flaky invite actions beyond configured limits.

