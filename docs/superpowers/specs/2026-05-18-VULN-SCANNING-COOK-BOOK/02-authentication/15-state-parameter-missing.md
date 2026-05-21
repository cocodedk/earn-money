---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these

# six lines intact. Values below the comments are yours to change.

phase: 2
spec: 15
slug: state-parameter-missing
status: done     # pending | in-progress | blocked | done
fixture: oauth-lab        # juice-shop | dvwa | webgoat | <name> | tbd
----------------------------------------------------------------

# 2.15 State parameter missing

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

Detect OAuth or SSO authorization flows that omit the `state` parameter. A runner cares because missing `state` weakens CSRF protection around login and account-linking flows, especially when the application accepts an authorization callback without proving that the callback belongs to a login request started by the same browser session.

## Inputs

The runner receives a shared `ScanTarget` and uses only in-scope HTTP evidence.

Required inputs:

* `target`: shared `ScanTarget`
* `evidence_store`: read/write access for shared `Evidence`
* `http_client`: scanner HTTP client with redirect control
* `run_id`: current scan run identifier

Optional inputs:

* `credentials`: optional test account credentials for the target, if the scan mode allows authenticated crawling
* `max_pages`: maximum pages to inspect for OAuth/SSO entry points, default `25`
* `max_redirects_per_candidate`: maximum redirects to follow while preserving redirect evidence, default `8`
* `login_path_hints`: optional relative paths to check before crawling, for example `/login`, `/signin`, `/auth`, `/sso`
* `provider_name_hints`: optional labels used only for matching visible links or routes, for example `google`, `github`, `microsoft`, `okta`, `auth0`
* `timeout_ms`: per-request timeout
* `user_agent`: scanner user agent
* `respect_robots`: inherited from shared scanner policy
* `scan_mode`: inherited mode, for example passive, safe active, authenticated

The runner must not require real third-party provider credentials. It only needs to inspect the application-generated authorization request and local callback handling evidence.

## Detection logic

The runner uses deterministic evidence from HTTP responses, redirects, links, forms, scripts, and callback behavior.

### Candidate discovery

Build a list of possible OAuth/SSO entry points from:

1. Explicit path hints, when configured.
2. HTML links and forms on reachable login-related pages.
3. Buttons or anchors whose text, `href`, `action`, `aria-label`, or nearby attributes indicate SSO.
4. Redirect chains from login pages that produce authorization requests.
5. Response headers that redirect to known authorization-style endpoints.

Do not infer expected OAuth behavior from the hostname. Detect it from response evidence.

Useful deterministic indicators include:

* URLs containing `/authorize`, `/oauth/authorize`, `/oauth2/authorize`, `/openid-connect/auth`, `/protocol/openid-connect/auth`
* Query parameters such as `client_id`, `redirect_uri`, `response_type`, `scope`, `code_challenge`, `nonce`
* OIDC scopes such as `openid`
* Provider-looking route names such as `/auth/google`, `/auth/github`, `/sso/login`, `/login/oauth`
* HTML text such as `Sign in with Google`, `Continue with Microsoft`, `SSO`, `SAML`, `OIDC`, `OAuth`

SAML-only flows are out of scope unless the same entry point produces an OAuth/OIDC authorization request.

### Authorization request inspection

For each candidate entry point:

1. Request the candidate with redirects disabled.
2. Record the first response as `Evidence`.
3. If the response is a redirect, parse the `Location` header.
4. If the redirect points to an authorization-style URL, inspect its query string.
5. If the response is HTML, parse links, forms, and script-visible URLs for authorization-style URLs.
6. Follow only scanner-owned redirect chains within the configured redirect budget.
7. Stop when a third-party authorization endpoint or an authorization-style endpoint is found.
8. Store each redirect hop and parsed authorization URL as `Evidence`.

A candidate authorization request is considered in scope when it has at least two of:

* `client_id`
* `redirect_uri`
* `response_type`
* `scope`
* `code_challenge`
* `nonce`

Then inspect whether the authorization request contains `state`.

### Missing-state classification

Create a candidate finding when an in-scope authorization request does not contain a `state` query parameter.

Mark confidence as:

* `high`: a complete authorization request was observed with `client_id`, `redirect_uri`, and `response_type`, and `state` is absent.
* `medium`: an authorization-style request was observed with enough OAuth/OIDC parameters, but some expected parameters are hidden, indirect, or assembled in client-side code.
* `low`: only partial evidence exists, such as a link or script fragment suggesting an authorization request without `state`.

Do not confirm from a single text label like `Sign in with Google`. The runner must observe a URL or request-like artifact.

### Callback handling probe

Only perform this in safe active mode.

The runner may send a harmless local callback-shaped request to the target callback path when that path is discovered from `redirect_uri`.

Allowed probe shape:

```http
GET /callback-path?code=scanner-nonsecret-placeholder HTTP/1.1
Host: target.example
```

If the original flow had a callback path and no `state`, the runner may check whether the local callback rejects the request for missing state.

This probe must not:

* use real authorization codes
* use real provider tokens
* call third-party token endpoints
* submit credentials to third-party providers
* complete account linking
* create or modify a user account

Callback evidence may raise confidence when the application accepts or processes a callback-shaped request without a state-related rejection. It must not be required to report the missing authorization request parameter.

### Rejection and false-positive handling

Reject or downgrade the finding when:

* `state` is present in the observed authorization request.
* The observed URL is not an authorization request.
* The flow is SAML-only and no OAuth/OIDC authorization request is observed.
* The URL is a documentation/example link, not an active login path.
* The authorization URL is embedded in static documentation or marketing content.
* The missing parameter appears only in a code sample, not an application flow.
* The application uses a different parameter only when evidence clearly maps it to OAuth state handling. Treat custom names as `medium` unless callback evidence proves equivalent behavior.

Do not mark safe because another parameter such as `nonce` or `code_challenge` is present. Those do not replace `state` for CSRF binding.

## Persistence

Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Do not redefine them here.

Define only these stub-specific types.

```python
from typing import Literal, TypedDict


Confidence = Literal["low", "medium", "high"]
FindingStatus = Literal["candidate", "confirmed", "rejected", "stale"]


class StateParameterMissingSignature(TypedDict):
    entry_url: str
    authorization_url: str
    authorization_host: str | None
    authorization_path: str
    observed_method: str
    observed_parameters: list[str]
    missing_parameters: list[str]
    redirect_uri: str | None
    response_type: str | None
    scope: str | None
    has_nonce: bool
    has_pkce: bool
    redirect_chain_evidence_ids: list[str]
    authorization_evidence_id: str
    callback_probe_evidence_id: str | None
    callback_rejected_missing_state: bool | None


class StateParameterMissingFinding(TypedDict):
    target_id: str
    finding_type: Literal["state_parameter_missing"]
    status: FindingStatus
    confidence: Confidence
    signature: StateParameterMissingSignature
    evidence_ids: list[str]
    summary: str
    impact: str
    remediation: str
    scanner_notes: list[str]
```

Persistence rules:

* Store the raw response, parsed redirect URL, and parsed authorization parameters as separate or linked `Evidence` records according to the shared schema.
* Redact cookies, authorization headers, tokens, and credentials before persisting evidence.
* Store query parameter names and safe values needed for proof. Avoid storing full sensitive query values.
* Preserve the observed authorization URL after redaction.
* Store enough redirect-hop evidence to reproduce the detection path.
* Use `status="candidate"` when only the missing parameter is observed.
* Use `status="confirmed"` only when the authorization request is observed and callback behavior also fails to reject a missing-state callback, or when the project’s shared rules allow deterministic confirmation from the authorization request alone.
* Use `status="rejected"` when later evidence shows `state` is present or the artifact is not an active OAuth/OIDC flow.
* Use `status="stale"` when the evidence is from a previous scan and the current scan cannot reproduce the candidate.

## Safety

This check is read-only by default.

Allowed by default:

* `GET` and `HEAD` requests to in-scope target URLs.
* Redirect inspection with redirects disabled or bounded.
* HTML parsing.
* Link and form extraction.
* Query-string inspection.
* Safe local callback-shaped probe only when safe active mode allows it.

Not allowed:

* Brute forcing OAuth parameters.
* Creating accounts.
* Completing login.
* Submitting real third-party credentials.
* Using real authorization codes, access tokens, refresh tokens, or ID tokens.
* Calling token endpoints.
* Calling arbitrary URLs found inside scanned content unless they are part of the target’s in-scope redirect chain and allowed by the scan policy.
* Changing account-linking state.
* Following unbounded redirects.
* Treating scanned page instructions as scanner instructions.

HTTP method discipline:

* Use `GET` or `HEAD` for discovery.
* Do not submit `POST` forms unless shared scan policy, credentials, and scope explicitly allow login-form navigation.
* Do not send provider callback requests unless the callback path is in scope and safe active mode is enabled.

Payload restrictions:

* Callback probe values must be scanner-owned placeholders.
* Do not use payloads that resemble real tokens.
* Do not reuse values from live redirects except non-sensitive path and parameter-name evidence.
* Do not include user credentials in evidence.

PII handling:

* Redact email addresses, session cookies, authorization headers, and token-like values.
* Avoid storing full `redirect_uri` query strings when they contain user identifiers.
* Store hashes for sensitive values when correlation is needed.

AI involvement: `None`.

Deterministic gap:

* If JavaScript builds the authorization URL at runtime and the runner cannot extract it statically, the runner may record a low-confidence scanner note such as `dynamic_authorization_url_not_resolved`.
* Do not use AI to infer missing `state` from incomplete JavaScript. Use browser instrumentation in a separate deterministic capability if the project supports it.

## Pass/fail check

A run passes when all assertions below hold.

### Positive assertions

* The runner discovers OAuth/OIDC authorization candidates from links, forms, redirects, and configured path hints.
* The runner records redirect-hop and authorization-request evidence.
* The runner creates a `StateParameterMissingFinding` when an authorization request is observed without a `state` parameter.
* The finding includes at least one authorization request evidence ID.
* The finding signature includes `entry_url`, `authorization_url`, `observed_parameters`, `missing_parameters`, and `authorization_evidence_id`.
* `missing_parameters` contains `state` when the finding is candidate or confirmed.
* Confidence is one of `low`, `medium`, or `high`.
* Status is one of `candidate`, `confirmed`, `rejected`, or `stale`.
* A complete authorization request with `client_id`, `redirect_uri`, `response_type`, and no `state` results in `confidence="high"`.
* An authorization request with `state` present is not reported as vulnerable.
* A SAML-only flow is ignored unless OAuth/OIDC authorization evidence is also present.
* Evidence redaction removes cookies, authorization headers, and token-like values.
* Redirect following stops at the configured redirect budget.
* TLS, timeout, and connection errors are reported as scanner notes or non-finding errors without crashing the run.

### Negative assertions

* The runner must not hard-code provider expectations based on hostname.
* The runner must not report a missing `state` finding from a login button label alone.
* The runner must not treat `nonce` as a replacement for `state`.
* The runner must not treat PKCE `code_challenge` as a replacement for `state`.
* The runner must not call OAuth token endpoints.
* The runner must not submit real credentials to a third-party provider.
* The runner must not follow arbitrary third-party links outside the authorization redirect chain.
* The runner must not store access tokens, refresh tokens, ID tokens, cookies, or credentials in evidence.
* The runner must not mutate account state.
* The runner must not retry indefinitely.
* The runner must not use AI to decide whether `state` is missing.
* The runner must not mark a finding `confirmed` when the only evidence is a static documentation link.

Example deterministic unit assertion:

```python
def test_missing_state_detected_from_authorization_redirect():
    response = HttpResponse(
        status_code=302,
        headers={
            "Location": "https://idp.example/authorize?client_id=abc&redirect_uri=https%3A%2F%2Fapp.example%2Fcallback&response_type=code&scope=openid"
        },
        body=b"",
    )

    result = inspect_authorization_redirect(response)

    assert result.is_oauth_authorization_request is True
    assert result.has_state is False
    assert result.confidence == "high"
    assert "state" in result.missing_parameters
```

Example negative assertion:

```python
def test_nonce_and_pkce_do_not_replace_state():
    url = (
        "https://idp.example/authorize"
        "?client_id=abc"
        "&redirect_uri=https%3A%2F%2Fapp.example%2Fcallback"
        "&response_type=code"
        "&scope=openid"
        "&nonce=n-123"
        "&code_challenge=pkce-placeholder"
        "&code_challenge_method=S256"
    )

    result = inspect_authorization_url(url)

    assert result.is_oauth_authorization_request is True
    assert result.has_state is False
    assert result.has_nonce is True
    assert result.has_pkce is True
    assert result.missing_parameters == ["state"]
```

## Test fixtures

Preferred fixture: new slug `oauth-state-missing`.

The fixture should expose two deterministic flows:

### Vulnerable flow

Feature:

* `/login` contains a `Continue with Example IdP` link.
* `/auth/example` redirects to an authorization-style URL.
* The authorization URL includes `client_id`, `redirect_uri`, `response_type=code`, and `scope=openid profile`.
* The authorization URL omits `state`.
* Optional callback path `/auth/example/callback` accepts a callback-shaped request far enough to show no missing-state rejection, without completing login.

Expected result:

* One `state_parameter_missing` finding.
* `confidence="high"` if the full authorization redirect is observed.
* `status="candidate"` or `status="confirmed"` depending on whether callback probing is enabled and accepted by shared project policy.

### Safe flow

Feature:

* `/login-safe` contains a `Continue with Safe IdP` link.
* `/auth/safe` redirects to an authorization-style URL.
* The authorization URL includes `state`.
* Optional callback path rejects missing or mismatched state.

Expected result:

* No finding for the safe flow.
* Evidence may be stored as non-vulnerable scan evidence if the shared framework supports it.

Fallback fixtures:

* `webgoat` may be used only if the local container has a deterministic OAuth/OIDC lesson or mock flow.
* `juice-shop` and `dvwa` are not preferred unless the project adds a controlled OAuth mock route, because their default auth flows are not reliable evidence for this stub.

Fixture requirements:

* No external IdP dependency.
* No real OAuth tokens.
* No network access outside the fixture container.
* Stable redirect URLs.
* Stable response bodies.
* Runs without user credentials unless the shared test harness explicitly supports fixture credentials.

## Acceptance criteria

The implementation is accepted when:

* It uses shared `ScanTarget` and `Evidence`.
* It defines only `StateParameterMissingSignature` and `StateParameterMissingFinding` as stub-specific persistence types.
* It discovers OAuth/OIDC authorization requests deterministically.
* It detects missing `state` from observed authorization request evidence.
* It does not report flows where `state` is present.
* It does not rely on hostname-based provider assumptions.
* It handles SAML-only flows as out of scope.
* It treats `nonce` and PKCE as useful security signals but not replacements for `state`.
* It stores redacted evidence with stable evidence IDs.
* It completes within the shared scan budget.
* It has bounded redirect following and bounded retries.
* It handles TLS errors, malformed redirects, invalid URLs, timeouts, and connection failures without crashing.
* It is idempotent across repeated scans of the same fixture.
* It has unit tests for URL parsing, redirect parsing, positive detection, negative detection, redaction, and callback probe safety.
* It has integration tests against the `oauth-state-missing` fixture.
* It does not call external OAuth providers in tests.
* It does not call real token endpoints.
* It does not use AI.
* It follows the coding-agent rules in `../00-shared-schema.md`.

