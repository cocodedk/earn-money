---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 16
slug: token-substitution
status: done     # pending | in-progress | blocked | done
fixture: oauth-lab        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.16 Token substitution

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
- Return raw markdown directly. Do NOT wrap the response in a ` ```markdown ` code fence`.
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

Detect OAuth or SSO flows where a token, authorization code, or session-bound OAuth artifact from one context can be substituted into another context and still be accepted. A runner cares because this can lead to account takeover, client confusion, tenant confusion, or login as the wrong user without knowing their password.

## Inputs

The runner receives a shared `ScanTarget` and emits shared `Evidence`.

Required input:

* `target`: shared `ScanTarget`
* `base_url`: normalized from `target`
* `run_id`: scanner run identifier
* `http_client`: scanner-owned client with redirect capture
* `cookie_jar`: isolated per test identity
* `allowed_methods`: must include `GET`; may include `POST` only when authenticated test accounts are provided and scope allows active auth testing

Optional input:

* `credentials.primary`: first scanner-owned test account
* `credentials.secondary`: second scanner-owned test account
* `oauth_config.authorization_url`: known authorization endpoint, when discovered earlier or provided by scope
* `oauth_config.callback_url`: expected callback URL, when known
* `oauth_config.client_id`: expected client ID, when known
* `oauth_config.issuer`: expected issuer, when known
* `oauth_config.scope`: requested OAuth scope, when known
* `oauth_config.response_type`: expected response type, such as `code`
* `oauth_config.pkce_enabled`: known or detected PKCE behavior
* `max_redirects`: default `10`
* `timeout_seconds`: default from shared runner settings
* `active_auth_allowed`: default `false`
* `token_capture_allowed`: default `false`; may be `true` only for scanner-owned test identities
* `redact_tokens`: default `true`

The runner must not use real user accounts, third-party personal accounts, leaked tokens, or credentials not issued for the test.

## Detection logic

Detection is deterministic and has two modes.

### Passive mode

Passive mode is always allowed when the target is in scope.

1. Fetch the target login and SSO entry points with `GET`.
2. Follow redirects within `max_redirects`.
3. Record redirect chain evidence:

   * status code
   * `Location` host and path
   * query parameter names
   * fragment parameter names
   * cookie names and security flags
   * response content type
   * redirect source and destination origin
4. Detect OAuth or SSO flow evidence without hard-coding hostnames:

   * query parameter names such as `client_id`, `redirect_uri`, `response_type`, `scope`, `state`, `code_challenge`, `code_challenge_method`, `nonce`, `id_token`, `access_token`, `code`, `issuer`, `iss`, `aud`
   * paths or forms containing generic OAuth/OIDC terms such as `/authorize`, `/oauth`, `/oidc`, `/sso`, `/saml`, `/callback`, `/token`
   * response headers or bodies that reference OpenID Connect discovery, authorization endpoints, callback handling, or token exchange
5. Mark the signature as `candidate` when an OAuth or SSO flow is detected but no safe substitution test was run.
6. Mark the signature as `rejected` when no OAuth, OIDC, SAML, or SSO-like flow evidence is found.

Passive mode must not claim confirmed token substitution.

### Active controlled mode

Active controlled mode requires:

* `active_auth_allowed=true`
* two scanner-owned test accounts
* permission to perform login and callback tests
* token or code capture allowed for scanner-owned accounts only

The runner performs a safe two-account substitution test:

1. Start a login flow for `credentials.primary`.
2. Capture the callback request after successful authentication.
3. Store only redacted token metadata unless full token storage is explicitly allowed by the secure evidence store.
4. Start a separate login flow for `credentials.secondary` in a fresh cookie jar.
5. Substitute one artifact from the primary flow into the secondary flow, one artifact at a time:

   * authorization `code`
   * `id_token`, only if present in a front-channel flow
   * `access_token`, only if present in a front-channel flow
   * `state`, only when testing session binding as part of this stub
   * `nonce`, only when visible and used by the flow
6. Submit the modified callback to the application callback endpoint.
7. Compare the outcome against the control callback:

   * accepted login
   * authenticated identity shown by the app
   * session cookie issued
   * redirect to logged-in area
   * error page
   * OAuth error response
   * unchanged unauthenticated state
8. Confirm a finding only when substituted primary-account material is accepted in the secondary flow and the resulting application session belongs to the wrong identity, wrong client, wrong tenant, or an authenticated state that should not exist.

The runner must test one substitution at a time. It must reset cookies between attempts.

### Evidence classification

Use these deterministic signals:

| Signal                                                                  | Meaning                        | Confidence    |
| ----------------------------------------------------------------------- | ------------------------------ | ------------- |
| OAuth/OIDC/SSO parameters found, no active test                         | Possible exposure only         | low           |
| Substituted artifact rejected with clear error                          | Not vulnerable for tested path | high rejected |
| Substituted artifact accepted but identity cannot be determined         | Possible issue; needs review   | medium        |
| Substituted artifact accepted and wrong identity/client/tenant is shown | Confirmed issue                | high          |
| Token accepted after logout or session reset                            | Confirmed session binding flaw | high          |
| Token or code accepted across different callback sessions               | Confirmed binding flaw         | high          |

Identity comparison must use deterministic evidence from the app, such as account email, user ID, profile endpoint response, tenant label, or scanner-owned marker value. Do not infer identity from hostname.

## Persistence

Use the shared `ScanTarget` and `Evidence` types from `../00-shared-schema.md`.

Define only these stub-specific types.

```python
TokenSubstitutionArtifactKind = Literal[
    "authorization_code",
    "id_token",
    "access_token",
    "state",
    "nonce",
    "unknown"
]

TokenSubstitutionStatus = Literal[
    "candidate",
    "confirmed",
    "rejected",
    "stale"
]

TokenSubstitutionConfidence = Literal[
    "low",
    "medium",
    "high"
]

class TokenSubstitutionSignature(BaseModel):
    signature_id: str
    target_id: str
    flow_url: str
    callback_url: str | None = None
    detected_protocol: Literal["oauth2", "oidc", "saml", "sso_like", "unknown"]
    artifact_kind: TokenSubstitutionArtifactKind
    parameter_name: str | None = None
    response_type: str | None = None
    client_id_observed: bool
    redirect_uri_observed: bool
    state_observed: bool
    nonce_observed: bool
    pkce_observed: bool
    front_channel_token_observed: bool
    substitution_attempted: bool
    substitution_accepted: bool | None = None
    identity_mismatch_observed: bool | None = None
    tenant_mismatch_observed: bool | None = None
    client_mismatch_observed: bool | None = None
    evidence_ids: list[str]
    created_at: datetime

class TokenSubstitutionFinding(BaseModel):
    finding_id: str
    target_id: str
    status: TokenSubstitutionStatus
    confidence: TokenSubstitutionConfidence
    title: str
    summary: str
    affected_flow_url: str
    affected_callback_url: str | None = None
    artifact_kind: TokenSubstitutionArtifactKind
    substituted_parameter: str | None = None
    expected_behavior: str
    observed_behavior: str
    impact: str
    evidence_ids: list[str]
    redaction_applied: bool
    scanner_owned_accounts_only: bool
    remediation: str
    created_at: datetime
    updated_at: datetime
```

Persistence rules:

* Store raw HTTP bodies only through the shared evidence pipeline.
* Redact token values, authorization codes, cookies, session IDs, and credentials before normal logs.
* Store token metadata only:

  * parameter name
  * token type when known
  * length
  * hash prefix from scanner-approved hashing utility
  * issuer/audience/subject claims only when safely decoded from scanner-owned tokens and allowed by policy
* Link every finding to one or more `Evidence` IDs.
* Do not store full tokens in `TokenSubstitutionFinding`.
* Mark old findings as `stale` when the same flow is no longer reachable or the callback behavior changes enough that previous evidence no longer applies.

## Safety

Default behavior is passive and read-only.

HTTP discipline:

* Passive mode uses `GET` only.
* Active mode may use `POST` only for scanner-owned login and OAuth callback flows.
* Do not brute force tokens, codes, nonces, state values, or PKCE values.
* Do not generate token guesses.
* Do not replay tokens from real users.
* Do not use leaked tokens.
* Do not test against production personal accounts.
* Do not call IdP token endpoints unless the scope explicitly allows it and credentials are scanner-owned.
* Do not attempt refresh-token exchange.
* Do not use token substitution to access data beyond a minimal identity/profile proof for scanner-owned accounts.
* Do not continue after a confirmed identity mismatch except to record evidence and clean up sessions.

Payload restrictions:

* Only substitute artifacts captured during the same scanner run from scanner-owned accounts.
* Substitute one artifact at a time.
* Keep the original request shape unchanged except for the artifact being tested.
* Preserve method, path, headers, and non-sensitive query/body parameters unless the test case requires a controlled cookie reset.
* Never add exploit payloads.
* Never add external callback URLs outside the configured target scope.

PII handling:

* Use synthetic test accounts where possible.
* Store account markers, not personal profile data.
* Redact emails unless the project already stores scanner-owned test account identifiers in evidence.
* Redact names, phone numbers, addresses, profile photos, tokens, cookies, and authorization codes.

AI involvement: `None`.

Deterministic gap:

* If the app does not expose a stable identity marker after login, the runner may return `candidate` with `medium` confidence and `requires_manual_review` in the surrounding orchestration layer. Do not use AI to infer identity.

## Pass/fail check

A runner passes this spec when all assertions below are true.

### Positive assertions

* It creates a `candidate` finding with `low` confidence when OAuth or SSO evidence is detected but active testing is not allowed.
* It creates a `rejected` finding with `high` confidence when active testing is allowed and all substituted artifacts are rejected.
* It creates a `confirmed` finding with `high` confidence when a substituted artifact from account A is accepted during account B’s flow and the resulting session is account A, account B in the wrong flow, a wrong tenant, a wrong client, or another authenticated state that should not exist.
* It records evidence for the original control flow and the substituted flow.
* It records which artifact kind was substituted.
* It records whether `state`, `nonce`, and PKCE were observed.
* It resets cookies between identities and between substitution attempts.
* It redacts tokens, codes, cookies, and credentials in logs and persisted findings.
* It links every signature and finding to shared `Evidence` IDs.
* It uses `confidence` values only from `low`, `medium`, or `high`.
* It uses `status` values only from `candidate`, `confirmed`, `rejected`, or `stale`.

### Negative assertions

* It must not confirm a finding from passive evidence alone.
* It must not hard-code a hostname or IdP name to decide expected behavior.
* It must not assume OAuth is present only because a path contains `login`.
* It must not use real user credentials.
* It must not use leaked, guessed, generated, or third-party tokens.
* It must not brute force authorization codes, state values, nonces, PKCE verifiers, passwords, or MFA codes.
* It must not test token substitution unless at least two scanner-owned identities are available.
* It must not reuse cookies between the two test identities.
* It must not perform more than one artifact substitution per request.
* It must not mutate user profile data, passwords, MFA settings, emails, roles, billing data, or tenant settings.
* It must not store full token values in normal logs or findings.
* It must not send captured tokens to AI.
* It must not call external callback URLs outside scan scope.
* It must not treat a generic OAuth error page as a vulnerability.
* It must not downgrade a previously confirmed finding to rejected unless fresh evidence shows the tested flow now rejects substitution.

## Test fixtures

Use a new fixture slug: `oauth-token-substitution`.

The fixture should expose a small OAuth/OIDC-like flow inside the container with two scanner-owned users.

Required fixture behavior:

* `/login` starts a normal authorization-code-style flow.
* `/authorize` issues a code bound to:

  * user ID
  * client ID
  * redirect URI
  * session ID
  * nonce when present
  * PKCE challenge when present
* `/callback` exchanges or validates the code.
* `/me` returns a deterministic scanner-owned identity marker, such as `user_a_marker` or `user_b_marker`.
* A safe vulnerable mode accepts a code or token from another browser session.
* A safe fixed mode rejects substituted artifacts.

Suggested fixture variants:

| Variant                            | Behavior                                                                   |
| ---------------------------------- | -------------------------------------------------------------------------- |
| `fixed-code-binding`               | Code is bound to session, client, redirect URI, and user                   |
| `vulnerable-code-substitution`     | Code from user A is accepted in user B callback flow                       |
| `vulnerable-id-token-substitution` | Front-channel `id_token` from user A is accepted for user B                |
| `vulnerable-state-not-bound`       | Callback accepts a valid code even when `state` belongs to another session |
| `pkce-enforced`                    | Substitution fails because verifier and challenge do not match             |
| `tenant-confusion`                 | Token from tenant A is accepted in tenant B context                        |

The tests should run only against the local fixture. They must not contact a real IdP.

## Acceptance criteria

* The runner is idempotent for the same target, fixture mode, and credentials.
* Passive mode completes within the shared unauthenticated scan budget.
* Active controlled mode completes within the shared authenticated scan budget.
* TLS errors, redirect loops, malformed redirects, missing callback URLs, and unsupported flows produce clean `candidate` or `rejected` outcomes, not crashes.
* Network failures are recorded as evidence with a non-confirmed status.
* Retries are bounded by shared runner policy.
* Token and cookie redaction is covered by tests.
* The runner works with isolated cookie jars for each identity.
* The runner handles query-string and form-post callback styles.
* The runner handles callback parameters in both query and fragment form when visible to the scanner.
* The runner does not depend on a specific IdP hostname, product name, or framework.
* The runner produces stable signatures so repeat scans update the same logical finding.
* The runner does not call AI.
* The runner does not make out-of-scope network calls.
* Confirmed findings include enough evidence for a developer to reproduce the issue with scanner-owned accounts.

