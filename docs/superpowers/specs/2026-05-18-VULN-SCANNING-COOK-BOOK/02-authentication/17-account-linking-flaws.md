---

# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 17
slug: account-linking-flaws
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.17 Account linking flaws

> Phase 2 — Authentication · Category: OAuth / SSO

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

Detect unsafe OAuth or SSO account-linking behavior where an existing local account can be attached to the wrong external identity, or where an external identity can be linked without a fresh, user-bound authorization step. A runner cares because these flaws can lead to account takeover, identity confusion, or login bypass even when the core OAuth callback flow appears to work.

## Inputs

The runner receives the shared `ScanTarget` plus optional authentication material and scan knobs.

Required:

* `target`: shared `ScanTarget`
* `base_url`: normalized from `target`
* `http_client`: scoped client with redirect control, cookie jar isolation, timeout, and TLS handling
* `evidence_store`: persistence sink for shared `Evidence`

Optional:

* `session_a`: authenticated session for a first test account owned by the scanner
* `session_b`: authenticated session for a second test account owned by the scanner
* `oauth_fixture_provider`: local or controlled OAuth/SSO provider used only in test fixtures
* `known_link_paths`: configured candidate paths, such as `/account/link`, `/settings/connections`, `/auth/link`, `/oauth/link`
* `known_unlink_paths`: configured candidate paths, such as `/account/unlink`, `/settings/connections/remove`
* `max_candidate_paths`: default `20`
* `max_redirects`: default `5`
* `request_timeout_ms`: default from shared scanner config
* `allow_mutating_link_tests`: default `false`
* `allow_fixture_mutation`: default `false`, may be true only for local fixtures or explicit test targets
* `same_site_probe`: default `true`
* `csrf_probe`: default `true`
* `state_binding_probe`: default `true`

Credential rules:

* Do not use real user accounts.
* Do not use real third-party IdPs during automated scans.
* Use only scanner-owned synthetic accounts or fixture identities.
* If the runner does not have two safe accounts, it must run only passive and read-only checks.

## Detection logic

Detection is deterministic and evidence-based. The runner must not infer expected OAuth behavior from the hostname. It must detect account-linking surfaces and compare response behavior.

### Candidate discovery

Build a candidate set from:

1. Explicitly configured `known_link_paths`.
2. Links and forms found in authenticated account/settings pages.
3. OAuth-like routes discovered from redirects, HTML, JavaScript route manifests, and response headers.
4. Common path tokens only as hints, not as proof.

Path and content indicators:

* `link account`
* `connect`
* `connected accounts`
* `social login`
* `single sign-on`
* `sso`
* `oauth`
* `oidc`
* `openid`
* `google`
* `github`
* `microsoft`
* `saml`
* `identity provider`
* `idp`

HTTP indicators:

* redirect to an authorization endpoint
* query parameters such as `client_id`, `redirect_uri`, `response_type`, `scope`, `state`, `nonce`, `code_challenge`
* callback paths containing `callback`, `oauth`, `oidc`, `sso`, or `saml`
* account settings pages that list connected providers

The runner must store evidence for every candidate it decides to test.

### Passive checks

Passive checks are allowed by default.

For each candidate link endpoint or account connection page, check whether the response indicates weak linking controls:

* a link action is exposed over `GET`
* a link action lacks CSRF token evidence in forms or headers
* a link action starts OAuth without a `state` parameter
* a link action starts OIDC without `nonce` when an ID token flow is detected
* `state` appears static across two scanner-owned sessions
* `state` appears reusable across repeated starts in the same session
* callback accepts provider/account identifiers directly in query parameters without an authorization code
* callback exposes user identity fields such as `email`, `sub`, `provider_user_id`, or `external_id` as client-controlled parameters
* linking UI does not require an authenticated local session
* linking UI is reachable from an unauthenticated session and starts a linking flow rather than a login flow

A passive result can produce a `candidate` finding. It can be `confirmed` only when the runner observes a deterministic unsafe state transition in a fixture or explicitly authorized test mode.

### Active fixture checks

Active checks are allowed only when `allow_mutating_link_tests=true` and the target is marked as a safe fixture or explicit test environment.

Use two scanner-owned accounts:

* Account A: local account currently authenticated in `session_a`
* Account B: separate scanner-owned account or fixture IdP identity
* Provider identity P: fixture-controlled external identity

The runner may test the following only against fixture IdPs or scanner-owned local IdP mocks.

#### Missing fresh local authentication

1. Login as Account A.
2. Locate the account-linking action.
3. Attempt to start the link flow.
4. Check whether the application requires fresh authentication, step-up, or explicit confirmation before linking.
5. Record whether the link action proceeds directly to provider authorization.

Finding signal:

* `candidate`: no fresh-auth challenge is visible.
* `confirmed`: a fixture link is completed without fresh local confirmation where the app exposes sensitive account linking.

#### Cross-session state binding failure

1. Start a link flow in `session_a`.
2. Capture the authorization request and `state`.
3. Start a separate link flow in `session_b`.
4. Attempt to complete `session_a` with `session_b` state or vice versa, using only fixture-controlled OAuth responses.
5. Compare status code, redirect destination, account connection page, and stored linked identity state.

Finding signal:

* `confirmed` if the application accepts a callback state that was issued to a different session and links the provider identity.

#### Callback accepts client-controlled identity

1. Identify callback endpoints from observed authorization redirects.
2. Send a callback request without a valid authorization code.
3. Include only harmless fixture values for identity-like parameters.
4. Do not include real tokens or external IdP data.
5. Check whether the application records a linked identity.

Finding signal:

* `confirmed` if a provider identity is linked from client-controlled callback parameters without server-side token exchange evidence.

#### Link action over unsafe method

1. Detect forms, links, and API calls that trigger linking.
2. Compare method and CSRF evidence.
3. For active fixtures only, replay the same action without the CSRF token or from a clean cross-site-like context.
4. Check whether linking starts or completes.

Finding signal:

* `candidate` if a state-changing link action is exposed through `GET`.
* `confirmed` if replay without CSRF protection changes link state.

### Non-findings and rejection

Create `rejected` findings when evidence shows a suspected issue is not present:

* link flow requires authenticated local session
* link flow uses per-session, non-reused `state`
* callback rejects missing or mismatched `state`
* callback rejects missing authorization code
* callback does not accept identity from client-controlled parameters
* link action requires CSRF token or equivalent same-site protection
* account-linking state does not change after unsafe replay attempt

Do not mark a target vulnerable because it uses OAuth, OIDC, SAML, or social login. The finding must be about the linking control.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them.

Define only the stub-specific signature and finding types.

```python
from dataclasses import dataclass, field
from typing import Literal

Confidence = Literal["low", "medium", "high"]
FindingStatus = Literal["candidate", "confirmed", "rejected", "stale"]

AccountLinkingFlawKind = Literal[
    "link_over_get",
    "missing_csrf_on_link",
    "missing_state",
    "static_or_reused_state",
    "state_not_bound_to_session",
    "callback_accepts_client_identity",
    "linking_without_local_session",
    "linking_without_fresh_auth",
    "unsafe_cross_account_link"
]

@dataclass(frozen=True)
class AccountLinkingFlawsSignature:
    kind: AccountLinkingFlawKind
    endpoint_url: str
    http_method: str
    provider_hint: str | None = None
    observed_parameters: list[str] = field(default_factory=list)
    state_observation: str | None = None
    csrf_observation: str | None = None
    session_observation: str | None = None
    mutation_observed: bool = False
    negative_control_observed: bool = False

@dataclass
class AccountLinkingFlawsFinding:
    target_id: str
    status: FindingStatus
    confidence: Confidence
    signature: AccountLinkingFlawsSignature
    evidence_ids: list[str]
    summary: str
    impact: str
    remediation: str
    first_seen_at: str
    last_seen_at: str
```

Evidence requirements:

* Store request and response metadata for every candidate tested.
* Store redacted URLs, methods, status codes, redirect locations, and relevant parameter names.
* Store hashes of response bodies where useful.
* Store only minimal body excerpts needed to prove the finding.
* Redact tokens, cookies, authorization codes, ID tokens, access tokens, refresh tokens, SAML assertions, session IDs, email addresses, and names unless the fixture identity is synthetic and explicitly marked safe.
* Link every finding to at least one `Evidence` item.
* A `confirmed` finding must include evidence of both the unsafe condition and the resulting accepted state transition or equivalent server response.

Suggested evidence labels:

* `account_linking.discovery.page`
* `account_linking.oauth.start`
* `account_linking.oauth.callback`
* `account_linking.state.cross_session`
* `account_linking.csrf.replay`
* `account_linking.connection_state.before`
* `account_linking.connection_state.after`
* `account_linking.negative_control`

## Safety

Default mode is read-only.

Allowed in default mode:

* GET settings/account pages.
* Parse forms and links.
* Start an OAuth authorization request only when this does not link an account by itself.
* Inspect redirects without following to real third-party login pages beyond the first authorization redirect.
* Compare generated `state` values across scanner-owned sessions when available.
* Send non-mutating callback probes that must not contain valid codes, tokens, assertions, or real identity values.

Blocked in default mode:

* Completing an OAuth or SSO link.
* Linking or unlinking real accounts.
* Calling real third-party IdP token endpoints.
* Using real user credentials.
* Sending valid authorization codes, access tokens, ID tokens, refresh tokens, or SAML assertions.
* Creating, deleting, or changing account connections.
* Testing against accounts not owned by the scanner.
* Brute forcing state, nonce, codes, tokens, or provider identifiers.
* Replaying many variants.

Allowed only when `allow_mutating_link_tests=true` and the environment is a safe fixture:

* Complete a link using fixture-controlled OAuth/SSO responses.
* Verify before/after connection state.
* Replay one CSRF-negative-control request.
* Test cross-session state binding with two scanner-owned sessions.

HTTP method discipline:

* Use `GET` only for discovery unless an endpoint is known to be a safe fixture.
* Use at most one mutating request per test case in fixture mode.
* Never retry mutating requests automatically.
* Do not follow redirects into real provider login pages with credentials.
* Stop when a response asks for human login, MFA, consent, captcha, or external provider interaction.

Payload restrictions:

* Use harmless fixture identifiers such as `fixture-provider-subject-a`.
* Do not place real emails, names, tokens, passwords, or customer data into callback parameters.
* Do not attempt token substitution across real identities.
* Do not attempt SAML assertion tampering in this stub.

PII handling:

* Treat linked account names, emails, provider subjects, and user IDs as sensitive.
* Store only redacted or hashed identity values unless the value is a known synthetic fixture identity.
* Do not include raw tokens or assertions in finding summaries.

AI involvement: `None`.

Named deterministic gap:

* If the app hides all account-linking behavior behind JavaScript that requires a browser runtime, this stub may return `candidate` evidence with `confidence="low"` and recommend a browser-based deterministic runner. Do not use AI to infer the missing behavior.

## Pass/fail check

The implementation passes when these assertions hold.

### Positive assertions

* Given an account settings page with a connected-account link, the runner records discovery evidence.
* Given an OAuth link start redirect without `state`, the runner creates a `candidate` finding with `kind="missing_state"`.
* Given two sessions that receive the same `state`, the runner creates a `candidate` finding with `kind="static_or_reused_state"`.
* Given a fixture app that accepts Session B state in Session A callback and links the account, the runner creates a `confirmed` finding with `kind="state_not_bound_to_session"`.
* Given a fixture callback that links an identity from client-controlled query parameters without a code exchange, the runner creates a `confirmed` finding with `kind="callback_accepts_client_identity"`.
* Given a link action over `GET`, the runner creates a `candidate` finding with `kind="link_over_get"`.
* Given a fixture link action that succeeds without CSRF token evidence, the runner creates a `confirmed` finding with `kind="missing_csrf_on_link"`.
* Given a link flow that requires fresh local authentication, the runner records a `rejected` finding or no finding for `linking_without_fresh_auth`.
* Given before/after connection state evidence showing no link change, the runner does not mark the issue as confirmed.
* Every finding has at least one shared `Evidence` reference.
* Every confirmed finding has evidence for the unsafe control and the accepted server behavior.
* Confidence is one of `low`, `medium`, or `high`.
* Status is one of `candidate`, `confirmed`, `rejected`, or `stale`.

### Negative assertions

* The runner must not use real third-party IdP credentials.
* The runner must not complete account linking outside fixture or explicitly authorized mutating mode.
* The runner must not link or unlink a real account.
* The runner must not brute force OAuth `state`, `nonce`, codes, tokens, or provider IDs.
* The runner must not send leaked, guessed, or harvested tokens.
* The runner must not infer vulnerability from provider name alone.
* The runner must not hard-code hostname-to-technology assumptions.
* The runner must not treat absence of visible OAuth UI as proof that no account-linking feature exists.
* The runner must not mark a passive observation as `confirmed` without state-change or rejection evidence.
* The runner must not store raw cookies, authorization headers, authorization codes, ID tokens, access tokens, refresh tokens, or SAML assertions.
* The runner must not retry mutating requests automatically.
* The runner must not follow real provider login flows that require user credentials, MFA, consent, or captcha.
* The runner must not call AI for detection.

## Test fixtures

Preferred fixture: `webgoat` with a new local OAuth/OIDC account-linking lesson or helper app.

If no existing fixture exposes the bug cleanly, create a new fixture slug:

* `account-linking-flaws`

Fixture requirements:

* Runs fully inside the test container.
* Uses a local mock OAuth/OIDC provider.
* Provides two scanner-owned local users.
* Provides two fixture provider identities.
* Exposes a safe account settings page with connected-account UI.
* Exposes vulnerable and safe variants behind separate paths or config flags.

Required vulnerable cases:

1. `GET /settings/connections/link/mock` starts or completes linking as a state-changing GET.
2. OAuth link start omits `state`.
3. OAuth link start reuses static `state`.
4. Callback accepts `state` issued to another session.
5. Callback accepts `provider_user_id` or equivalent client-controlled identity without code exchange.
6. Link action accepts POST without CSRF token.
7. Link action succeeds without fresh local confirmation for sensitive relinking.

Required safe cases:

1. Link flow requires authenticated local session.
2. Link flow uses per-session `state`.
3. Callback rejects missing `state`.
4. Callback rejects cross-session `state`.
5. Callback rejects missing or invalid authorization code.
6. Callback ignores client-controlled identity fields.
7. Link action requires CSRF token or equivalent protection.
8. Sensitive relinking requires fresh local authentication or explicit confirmation.

Fixture evidence should expose before/after connection state through a scanner-only endpoint or page, such as:

* `/settings/connections`
* `/__fixture/account-state`

The fixture must not depend on external network access.

## Acceptance criteria

* The stub is idempotent in read-only mode.
* The stub does not mutate account-linking state unless explicitly allowed and running against a safe fixture.
* The stub completes within the configured request and candidate-path budget.
* The stub handles TLS errors, connection failures, invalid redirects, missing cookies, and malformed HTML gracefully.
* The stub records useful evidence for discovery, tested candidates, negative controls, and confirmed findings.
* The stub redacts tokens, cookies, assertions, codes, credentials, and PII before persistence.
* The stub uses deterministic HTTP evidence only.
* The stub produces stable results across repeated runs against the same fixture.
* The stub uses isolated cookie jars for each scanner-owned session.
* The stub enforces a strict retry cap and never retries mutating requests.
* The stub distinguishes `candidate` from `confirmed`.
* The stub reports `stale` when a previously persisted finding no longer has matching evidence.
* The stub keeps scanner-owned fixture identities separate from real accounts.
* The stub follows the shared coding-agent rules in `../00-shared-schema.md`.
* Unit tests cover passive discovery, missing state, static state, cross-session state acceptance, unsafe callback identity, GET link actions, missing CSRF, safe rejection paths, evidence redaction, and mutation gating.
* Integration tests run without external IdP access.

