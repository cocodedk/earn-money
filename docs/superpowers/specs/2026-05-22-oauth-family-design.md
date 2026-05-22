# Phase 2 OAuth/OIDC Family — Design

> Stubs 2.14 redirect-uri-issues, 2.15 state-parameter-missing,
> 2.16 token-substitution, 2.17 account-linking-flaws.
> Stubs 2.21–2.22 (invitation/tenant) are deferred to a separate plan.

## Fixture architecture

One Docker image (`earnmoney-oauth-lab:dev`) built from
`fixtures/oauth-lab/`. Four named compose services differentiated by
the `SCENARIO` env var. All listen on port 3000; DNS name on
`scanner-net` provides isolation (no distinct internal ports needed).

### File layout

```
fixtures/oauth-lab/
  server.js            # entry: load SCENARIO, mount router, ≤80 lines
  scenarios/
    redirect-uri.js    # intentional vulns for 2.14
    state-missing.js   # intentional vulns for 2.15
    token-sub.js       # intentional vulns for 2.16
    account-link.js    # intentional vulns for 2.17
  lib/
    oauth-helpers.js   # OIDC metadata, state gen, client registry ≤150 lines
    session.js         # in-memory session store ≤80 lines
```

Each scenario file is ≤200 lines. `lib/` contains only boring protocol
plumbing. Intentional vulnerabilities live exclusively in `scenarios/`.

### Required endpoints on every scenario

| Route | Purpose |
|-------|---------|
| `GET /healthz` | Liveness check for compose `depends_on` |
| `GET /fixture-info` | Returns `{"scenario": "<name>"}` |
| `POST /reset` | Wipes in-memory state (required for 2.16/2.17 test isolation) |

Server crashes on startup if `SCENARIO` is missing or unknown.

### Provider vs RP framing

- **2.14** — fixture is the **authorization server** (provider side):
  strict vs loose `redirect_uri` validation variants.
- **2.15** — fixture is the **client app** (RP side): generates auth
  requests that omit `state`.
- **2.16/2.17** — fixture plays **both** roles: mock IdP + vulnerable
  RP callback handler.

### Compose services

```yaml
oauth-redirect-uri-lab:
  image: earnmoney-oauth-lab:dev
  environment:
    SCENARIO: redirect-uri
  networks: [scanner-net]

oauth-state-missing:
  image: earnmoney-oauth-lab:dev
  environment:
    SCENARIO: state-missing
  networks: [scanner-net]

oauth-token-substitution-lab:
  image: earnmoney-oauth-lab:dev
  environment:
    SCENARIO: token-sub
  networks: [scanner-net]

oauth-account-linking-lab:
  image: earnmoney-oauth-lab:dev
  environment:
    SCENARIO: account-link
  networks: [scanner-net]
```

Fixture URLs wired into **both** `backend` and `worker` env blocks:

```
FIXTURE_OAUTH_REDIRECT_URI_URL=http://oauth-redirect-uri-lab:3000
FIXTURE_OAUTH_STATE_MISSING_URL=http://oauth-state-missing:3000
FIXTURE_OAUTH_TOKEN_SUB_URL=http://oauth-token-substitution-lab:3000
FIXTURE_OAUTH_ACCOUNT_LINK_URL=http://oauth-account-linking-lab:3000
```

### Scope / RoE

Four `programs/local/` entries (one per scenario service), matching
the `reset-canary` + `webgoat` pattern already in the repo.

## Python stub structure

Each stub follows the established Phase 2 layout:

```
backend/apps/stubs/2_14_redirect_uri/
  runner.py        # discover + probe + classify
  models.py        # Signature + Finding Django models
  tests/
    test_runner.py
    test_models.py
```

All stubs import from `_shared/auth/` (discovery, scope_check,
submit_probe, log_finding_candidate). Stubs 2.16/2.17 may add
`_shared/auth/oauth_session.py` for two-cookie-jar flows if the
shared primitive is needed by both; otherwise it stays in the stub.

## Implementation order

| Order | Stub | Key constraint |
|-------|------|---------------|
| 1 | 2.15 state-missing | Passive GET only; simplest fixture scenario |
| 2 | 2.14 redirect-uri | GET probes; 8 mutation classes; URL parser |
| 3 | 2.16 token-sub | Two test-client sessions; first active-auth stub |
| 4 | 2.17 account-link | Full session-linked callback; heaviest |

## Testing

- **Unit tests**: URL parsing, classification, redaction, all negative
  assertions, confidence rules.
- **Integration tests**: run against the named compose service;
  assert intentional vulns are present; call `/reset` between tests.
- **Fixture tests**: verify `/healthz`, `/fixture-info`, `/reset` work
  and each scenario's intentional vuln is reachable.
- **Coverage**: 100% line+branch on all stub production code.
  Fixture JS is dev tooling — exempt per CLAUDE.md.
- **Review gates**: `/codex-review` (gpt-5.5 xhigh) after each stub
  family, then `/code-review high` until clean before moving on.

## Deferred

Stubs 2.21 (invitation-abuse) and 2.22 (tenant-org-join-abuse) need a
multi-tenant signup fixture and will be planned separately.
