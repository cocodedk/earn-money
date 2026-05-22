---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 22
slug: tenant-org-join-abuse
status: done     # pending | in-progress | blocked | done
fixture: tenant-org-join-abuse-lab        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.22 Tenant/org join abuse

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

Detect registration and invitation flows that let an unauthorised user join an existing tenant, workspace, organisation, company account, or team without a valid invitation, verified domain ownership, admin approval, or other intended control. The runner cares because this can give an external user access to tenant-scoped data, internal users, billing settings, integrations, project metadata, or collaboration spaces.

## Inputs

The runner receives a shared `ScanTarget` and optional registration configuration.

Required input:

* `ScanTarget` from `../00-shared-schema.md`
* Base URL in scope
* HTTP client with redirect handling, cookie jar isolation, TLS controls, and evidence capture
* Scanner policy showing whether account creation is allowed

Optional input:

* `primary_account`: a valid test account already inside the target tenant
* `secondary_account`: a separate synthetic account not already inside the tenant
* `known_tenant_identifier`: tenant slug, workspace slug, org ID, invite URL, or team name supplied by the user
* `allowed_email_domains`: domains the scanner may use for synthetic accounts
* `disallowed_email_domains`: domains the scanner must never use
* `registration_canary_prefix`: prefix for generated emails and display names
* `max_join_attempts`: default `3`
* `allow_registration_mutation`: default `false`
* `allow_invite_acceptance`: default `false`
* `allow_tenant_join_attempt`: default `false`
* `cleanup_hint`: optional path or API action the fixture can expose for deleting test users

Configuration knobs:

```ts
export type TenantOrgJoinAbuseConfig = {
  allow_registration_mutation: boolean;
  allow_invite_acceptance: boolean;
  allow_tenant_join_attempt: boolean;
  max_join_attempts: number;
  registration_canary_prefix: string;
  known_tenant_identifier?: string;
  allowed_email_domains?: string[];
  disallowed_email_domains?: string[];
  cleanup_hint?: string;
};
```

The scanner must not infer tenant expectations from hostname, brand, product name, favicon, framework, or vendor strings. It may only infer join behaviour from observed responses, forms, redirects, API responses, session state, and supplied configuration.

## Detection logic

Use deterministic checks only. Start with passive discovery. Perform mutating checks only when policy allows them.

### 1. Discover tenant and join surfaces

Fetch the target root and likely auth routes with `GET` only:

* `/`
* `/login`
* `/signin`
* `/register`
* `/signup`
* `/join`
* `/invite`
* `/invitations`
* `/accept-invite`
* `/team`
* `/workspace`
* `/organization`
* `/org`

Also inspect links and forms discovered from the returned HTML.

Record evidence for:

* registration forms
* invite acceptance forms
* tenant slug or workspace fields
* organisation selector fields
* `company`, `organization`, `org`, `tenant`, `workspace`, `team`, `domain`, `invite`, `invitation`, `code`, `token`, `join` parameter names
* API routes referenced by scripts or forms
* redirects to tenant-scoped paths such as `/org/{slug}`, `/workspace/{slug}`, `/team/{slug}`

Do not classify a route as vulnerable based only on words in HTML. The finding needs a state transition or an explicit server response that shows unauthorised tenant membership.

### 2. Establish tenant baseline where possible

If `primary_account` is supplied, log in with it and collect tenant evidence:

* tenant display name
* tenant slug or ID
* member list visibility, if available
* invite page visibility, if available
* current user identity
* visible projects, dashboards, billing, settings, or member pages

The runner must store only minimal snippets in `Evidence`. Do not store full member lists unless the fixture requires it. Redact personal emails except synthetic scanner accounts.

If no authenticated tenant baseline is available, the check may still report weak signals, but confidence must stay `low` or `medium` unless the server confirms unauthorised tenant membership.

### 3. Test unauthorised self-join with synthetic account

Only run this step when all are true:

* `allow_registration_mutation=true`
* `allow_tenant_join_attempt=true`
* a synthetic `secondary_account` is supplied or can be generated from an allowed test domain
* a tenant identifier is supplied or discovered from authenticated baseline evidence

Attempt one controlled registration or join flow using the secondary account.

Supported deterministic probes:

* Submit registration with a tenant/workspace/org field set to the known tenant identifier.
* Submit registration with an email domain matching the tenant’s domain only if the scanner owns that synthetic domain or the user explicitly supplied it as allowed.
* Visit an invite or join URL without a valid invite token.
* Attempt invite acceptance with missing, blank, random, expired, or reused token values.
* Attempt API join endpoint with known tenant slug or ID and no invite token.
* Attempt API join endpoint with a random invite code and known tenant slug.

Payload restrictions:

* Use only synthetic scanner accounts.
* Use at most `max_join_attempts`.
* Use random invite tokens generated by the scanner.
* Do not brute force invite codes.
* Do not enumerate tenant IDs.
* Do not try real user emails.
* Do not try leaked, guessed, or harvested domains.
* Do not send password reset, MFA, or email verification abuse payloads from this stub.

### 4. Confirm membership transition

After the join attempt, authenticate as the secondary account and fetch a tenant-scoped page or API endpoint.

A confirmed issue requires at least one of these:

* secondary account is redirected into the existing tenant without a valid invitation
* secondary account receives a session claim, JSON field, or page value containing the existing tenant ID or slug
* secondary account can access member, project, dashboard, billing, settings, or tenant-scoped API content belonging to the existing tenant
* primary account’s member list or audit log shows the secondary account joined without admin approval or valid invite evidence
* server returns a success response such as `joined`, `member_created`, `workspace_member`, or equivalent with the known tenant identifier

Candidate issue signals:

* registration form accepts a tenant slug field and returns generic success, but membership is not proven
* invite endpoint accepts missing or random token and returns a weak success page, but tenant access is not proven
* server exposes join endpoints with predictable tenant identifiers, but join was not attempted because mutation was disabled

Rejected signals:

* secondary account is placed in its own new tenant
* server requires verified email before membership and tenant access is blocked
* server requires valid invite token
* server requires admin approval
* server returns pending state with no tenant data access
* server blocks joining by domain unless domain ownership or SSO verification succeeds

### 5. Status and confidence rules

Set `status` and `confidence` deterministically:

* `confirmed`, `high`: unauthorised secondary account gains access to existing tenant-scoped content.
* `confirmed`, `medium`: server confirms membership in existing tenant, but tenant data access is limited or not checked.
* `candidate`, `medium`: join endpoint appears to accept missing/random token, but scanner could not complete authentication or verification.
* `candidate`, `low`: passive evidence suggests risky self-join flow, but no state change was attempted.
* `rejected`, `high`: tested flow requires valid invite, admin approval, verified domain, or creates a separate tenant.
* `stale`, `low`: previous evidence no longer reproduces or route now returns 404/410.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only the stub-specific signature and finding types.

```ts
export type TenantOrgJoinAbuseJoinMethod =
  | "registration_tenant_field"
  | "domain_based_auto_join"
  | "invite_url_without_token"
  | "invite_url_random_token"
  | "api_join_without_invite"
  | "api_join_random_invite"
  | "unknown";

export type TenantOrgJoinAbuseControlState =
  | "missing"
  | "invite_required"
  | "admin_approval_required"
  | "email_verification_required"
  | "domain_ownership_required"
  | "sso_required"
  | "separate_tenant_created"
  | "unknown";

export type TenantOrgJoinAbuseSignature = {
  name: "TenantOrgJoinAbuseSignature";
  version: "1.0";
  target: ScanTarget;
  join_method: TenantOrgJoinAbuseJoinMethod;
  tenant_identifier_observed: boolean;
  tenant_identifier_kind?: "slug" | "id" | "domain" | "invite_url" | "unknown";
  tested_with_secondary_account: boolean;
  mutation_performed: boolean;
  control_state: TenantOrgJoinAbuseControlState;
  evidence_ids: string[];
};

export type TenantOrgJoinAbuseFinding = {
  name: "TenantOrgJoinAbuseFinding";
  status: "candidate" | "confirmed" | "rejected" | "stale";
  confidence: "low" | "medium" | "high";
  severity: "low" | "medium" | "high" | "critical";
  target: ScanTarget;
  signature: TenantOrgJoinAbuseSignature;
  evidence: Evidence[];
  title: string;
  summary: string;
  impact: string;
  remediation: string;
  joined_existing_tenant: boolean;
  tenant_access_observed: boolean;
  synthetic_account_used?: string;
  created_test_account: boolean;
  cleanup_required: boolean;
  safety_notes: string[];
};
```

Persistence rules:

* Store request and response metadata needed to reproduce the decision.
* Store exact status code, method, path, redirect chain, response content type, and stable evidence IDs.
* Store short body snippets only where they prove the result.
* Redact cookies, access tokens, invite tokens, CSRF tokens, session IDs, passwords, and real user emails.
* Do not persist full tenant member lists.
* Store synthetic account identifiers only when needed for cleanup and audit.
* Link all findings to evidence IDs. A finding without evidence IDs must be rejected before persistence.

## Safety

This stub is mostly passive by default. Joining an organisation is mutating and must be explicitly enabled.

Default behaviour:

* `GET` discovery only
* no account creation
* no invite acceptance
* no tenant join attempt
* no email verification bypass
* no brute forcing
* AI: `None`

Mutating behaviour is allowed only when configured by policy:

* `allow_registration_mutation=true` for creating synthetic accounts
* `allow_invite_acceptance=true` for using a supplied invite URL or fixture token
* `allow_tenant_join_attempt=true` for attempting to join a known tenant

HTTP method discipline:

* Use `GET` and `HEAD` for discovery.
* Use `POST` only for explicit registration, login, invite acceptance, or join actions when mutation is enabled.
* Do not use `PUT`, `PATCH`, or `DELETE` unless a fixture-specific cleanup hook is supplied and explicitly allowed.
* Do not follow cross-origin join or callback URLs unless they are inside the `ScanTarget` scope.

Payload restrictions:

* Use synthetic scanner accounts only.
* Use strong random passwords for synthetic accounts.
* Do not use real employee names, real customer domains, or real user emails.
* Do not brute force invite codes, tenant IDs, or workspace slugs.
* Do not enumerate organisations.
* Do not exploit access after membership is proven.
* Stop after the first confirmed unauthorised join.
* Use bounded retries only for network errors, not for guessing.

PII handling:

* Redact non-synthetic email addresses.
* Redact member names unless they are the scanner’s synthetic accounts.
* Store tenant identifiers only as needed to prove the finding.
* Never store credentials in evidence.

AI involvement:

* AI is `None`.
* A future AI-assisted classifier may only summarise already persisted deterministic evidence.
* AI must not decide whether a tenant join succeeded.
* AI must not propose new join payloads.
* AI must not handle raw tokens, cookies, passwords, or full tenant data.

Deterministic gap:

* Some products require email verification or admin approval outside HTTP-visible state. If the scanner cannot observe the final approval state, it must report `candidate` with `low` or `medium` confidence, not `confirmed`.

## Pass/fail check

The implementation passes when these assertions hold.

### Positive assertions

* The runner discovers registration, invite, and join surfaces using scoped HTTP evidence.
* The runner can operate in passive-only mode without creating accounts or joining tenants.
* The runner only performs account creation when `allow_registration_mutation=true`.
* The runner only attempts tenant join when `allow_tenant_join_attempt=true`.
* The runner only accepts or tests invite flows when `allow_invite_acceptance=true`.
* A confirmed finding requires evidence that the secondary synthetic account joined or accessed the existing tenant.
* Candidate findings clearly state what was observed and what was not proven.
* Rejected findings record the control that blocked abuse when known.
* Evidence includes status codes, paths, redirect chains, content type, and short proof snippets.
* Confidence follows the rules in Detection logic.
* `Evidence` and `ScanTarget` are imported from the shared schema.
* Only `TenantOrgJoinAbuseSignature` and `TenantOrgJoinAbuseFinding` are defined locally.
* The scanner redacts cookies, tokens, passwords, CSRF values, and real user emails.
* The scanner stops after one confirmed unauthorised join.

### Negative assertions

* The runner must not brute force invite codes.
* The runner must not enumerate tenant IDs, org slugs, or workspace names.
* The runner must not test against real user accounts.
* The runner must not infer vulnerability from hostname, product name, or expected SaaS behaviour.
* The runner must not create accounts unless mutation is explicitly enabled.
* The runner must not join a tenant unless join attempts are explicitly enabled.
* The runner must not mark a finding as confirmed from a registration success page alone.
* The runner must not mark a finding as confirmed when the secondary account is placed into a new separate tenant.
* The runner must not mark a finding as confirmed when admin approval, verified email, SSO, or domain ownership blocks tenant access.
* The runner must not store raw cookies, invite tokens, access tokens, passwords, or full member lists.
* The runner must not continue exploring tenant data after proof is established.
* The runner must not call external domains discovered in scanned content.
* The runner must not use AI to decide success or generate payloads.

## Test fixtures

Use a new fixture slug: `tenant-org-join-abuse`.

The fixture should expose a small multi-tenant app with registration, login, tenant dashboard, and member list pages.

Required fixture users:

* `owner@example.test`: existing tenant owner
* `member@example.test`: existing tenant member
* `outside@example.test`: account not initially in the tenant
* scanner-generated account support using `scanner+<random>@example.test`

Required fixture tenant:

* tenant name: `Acme Test Tenant`
* tenant slug: `acme`
* tenant ID: stable fixture value

Fixture routes:

* `GET /signup`: registration form with optional `workspace` field
* `POST /signup`: creates a user
* `GET /login`: login form
* `POST /login`: creates session
* `GET /workspace/acme`: tenant dashboard
* `GET /workspace/acme/members`: member list
* `POST /api/workspaces/acme/join`: vulnerable join endpoint in vulnerable mode
* `POST /api/workspaces/acme/join-secure`: secure join endpoint requiring invite token or admin approval
* `GET /invite/:token`: invite acceptance page
* `POST /invite/:token/accept`: accepts valid fixture invite only
* `POST /test/reset`: fixture-only cleanup endpoint, available only in local test mode

Vulnerable behaviour:

* `POST /api/workspaces/acme/join` adds any authenticated user to `acme` without invite token, admin approval, email verification, or domain ownership.
* After joining, `outside@example.test` or a scanner-created account can access `/workspace/acme` and see a tenant marker.
* The response contains a deterministic marker such as `workspace_member=true`.

Secure behaviour:

* `POST /api/workspaces/acme/join-secure` returns `403` unless a valid invite token is supplied.
* Missing, blank, random, expired, or reused invite token attempts do not create membership.
* Secure registration without invite creates a separate tenant or a pending account, not membership in `acme`.

Fixture evidence markers:

* `TENANT_ORG_JOIN_ABUSE_VULNERABLE`
* `TENANT_ORG_JOIN_ABUSE_JOINED_EXISTING_TENANT`
* `TENANT_ORG_JOIN_ABUSE_INVITE_REQUIRED`
* `TENANT_ORG_JOIN_ABUSE_PENDING_APPROVAL`
* `TENANT_ORG_JOIN_ABUSE_SEPARATE_TENANT_CREATED`

The fixture must be resettable and idempotent. Test accounts created by the scanner must be removable through the local cleanup route or isolated by random email.

## Acceptance criteria

Operational acceptance:

* Passive mode completes without side effects.
* Mutating mode creates at most one synthetic account per run unless the fixture reset requires a second bounded attempt.
* The scanner completes within the project’s normal per-target budget.
* The scanner handles TLS errors, connection refused, invalid redirects, malformed HTML, non-JSON API responses, and CSRF failures gracefully.
* Network retries are bounded and do not repeat successful mutating requests.
* Join attempts are capped by `max_join_attempts`.
* The scanner uses isolated cookie jars for primary and secondary accounts.
* The scanner does not leak session state between accounts.
* The scanner records enough evidence to reproduce the finding without storing secrets.
* The scanner marks stale findings when previously vulnerable routes no longer reproduce.
* The scanner is deterministic across repeated fixture runs.
* Tests cover passive discovery, vulnerable join, secure invite-required flow, admin-approval flow, separate-tenant flow, mutation-disabled mode, redaction, cleanup, and retry limits.
* No test calls external services.
* No test depends on wall-clock timing except bounded timeout handling.
* The implementation follows `../00-shared-schema.md` coding-agent rules.
* The final scanner result contains either one clear finding or a rejected result explaining why no issue was confirmed.

