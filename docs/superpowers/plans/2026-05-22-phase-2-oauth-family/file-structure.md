# File structure

## New files

### Fixture

```
fixtures/oauth-lab/
  Dockerfile                    # identical pattern to reset-canary
  package.json                  # express 4.21, no nodemailer
  server.js                     # entry: SCENARIO → mount router; /healthz /fixture-info /reset
  lib/
    oauth-helpers.js            # OIDC metadata builder, state gen, client registry, URL utils
    session.js                  # in-memory session store + /reset wipe
  scenarios/
    state-missing.js            # vulnerable + safe login→auth-redirect flows (stub 2.15)
    redirect-uri.js             # strict/loose-host/loose-path/foreign/preserves-invalid endpoints
    token-sub.js                # two-user login+authorize+callback+/me (stub 2.16)
    account-link.js             # settings/connections with safe+vulnerable link flows (stub 2.17)
```

All fixture JS files ≤200 lines. Split helpers into `lib/` sub-files if a
scenario grows too large.

### Programs

```
programs/local/oauth-state-missing/scope.md
programs/local/oauth-state-missing/roe.md
programs/local/oauth-redirect-uri-lab/scope.md
programs/local/oauth-redirect-uri-lab/roe.md
programs/local/oauth-token-substitution-lab/scope.md
programs/local/oauth-token-substitution-lab/roe.md
programs/local/oauth-account-linking-lab/scope.md
programs/local/oauth-account-linking-lab/roe.md
```

## Modified files

### docker-compose.yml

Add four services (all `image: earnmoney-oauth-lab:dev`):
`oauth-state-missing`, `oauth-redirect-uri-lab`,
`oauth-token-substitution-lab`, `oauth-account-linking-lab`.
Wire `FIXTURE_OAUTH_*_URL` into both `backend` and `worker` env blocks.

### Stub files (skeleton → full implementation)

```
backend/apps/stubs/oauth_missing_state/
  runner.py            # MODIFY: add detection chain after gate scaffold
  classify.py          # CREATE: inspect_authorization_url(), classify_state_missing()
  tests/
    test_gates.py      # EXISTS: gate tests already pass — do not break
    test_classify.py   # CREATE: unit tests for classify.py
    test_runner.py     # CREATE: end-to-end tests against fixture

backend/apps/stubs/oauth_redirect_uri/
  runner.py            # MODIFY: add detection chain
  mutate.py            # CREATE: generate_mutations(baseline_redirect_uri, scanner_origin)
  classify.py          # CREATE: classify_redirect_response(response, mutated_origin)
  tests/
    test_gates.py      # EXISTS — do not break
    test_mutate.py     # CREATE
    test_classify.py   # CREATE
    test_runner.py     # CREATE

backend/apps/stubs/oauth_token_substitution/
  runner.py            # MODIFY
  classify.py          # CREATE: classify_passive_oauth_evidence()
  submit.py            # CREATE: two-account substitution probe (active mode only)
  tests/
    test_gates.py      # EXISTS — do not break
    test_classify.py   # CREATE
    test_submit.py     # CREATE (active path, mocked)
    test_runner.py     # CREATE

backend/apps/stubs/oauth_account_linking/
  runner.py            # MODIFY
  classify.py          # CREATE: classify_link_flaw()
  tests/
    test_gates.py      # EXISTS — do not break
    test_classify.py   # CREATE
    test_runner.py     # CREATE
```

### Potential new shared primitive

`backend/apps/stubs/_shared/auth/oauth_session.py` — isolated two-cookie-jar
flow helper. Create only if both 2.16 and 2.17 need the same abstraction.
Decide after stub 2.16 is written; do not pre-create.
