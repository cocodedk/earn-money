# Task 06 — Programs scope+RoE + docker-compose wiring

Register scope/RoE for each oauth-lab scenario service and add the
four compose services. Wire env vars to both backend and worker.

**Files:**
- Create: `programs/local/oauth-state-missing/scope.md`
- Create: `programs/local/oauth-state-missing/roe.md`
- Create: `programs/local/oauth-redirect-uri-lab/scope.md`
- Create: `programs/local/oauth-redirect-uri-lab/roe.md`
- Create: `programs/local/oauth-token-substitution-lab/scope.md`
- Create: `programs/local/oauth-token-substitution-lab/roe.md`
- Create: `programs/local/oauth-account-linking-lab/scope.md`
- Create: `programs/local/oauth-account-linking-lab/roe.md`
- Modify: `docker-compose.yml`

---

- [ ] **Step 1: Write `programs/local/oauth-state-missing/scope.md`**

```markdown
---
platform: local
slug: oauth-state-missing
policy: rate-limited-OK
in_scope:
  - oauth-state-missing
out_of_scope: []
scope_hash: ""
last_synced: "2026-05-22T00:00:00Z"
---

# oauth-state-missing fixture

Operator-owned oauth-lab container (SCENARIO=state-missing).
Exposes a vulnerable login→auth redirect that omits `state`, and a
safe variant that includes `state`.
```

- [ ] **Step 2: Write `programs/local/oauth-state-missing/roe.md`**

```markdown
---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - oauth-state-missing
authorized_test_accounts: []
special_notes: |
  Passive GET-only fixture. No credentials needed.
  allow_oauth_probes enables stub 2.15 detection chain.
allow_active_login_probes: false
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-state-missing

OAuth passive discovery probe enabled. No mutation or account actions.
```

- [ ] **Step 3: Write scope+RoE for oauth-redirect-uri-lab**

`programs/local/oauth-redirect-uri-lab/scope.md`:
```markdown
---
platform: local
slug: oauth-redirect-uri-lab
policy: rate-limited-OK
in_scope:
  - oauth-redirect-uri-lab
out_of_scope: []
scope_hash: ""
last_synced: "2026-05-22T00:00:00Z"
---

# oauth-redirect-uri-lab fixture

Operator-owned oauth-lab container (SCENARIO=redirect-uri).
Exposes strict/loose/foreign authorization endpoint variants.
```

`programs/local/oauth-redirect-uri-lab/roe.md`:
```markdown
---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - oauth-redirect-uri-lab
authorized_test_accounts: []
special_notes: |
  GET-only probes. allow_pre_auth_redirect_probe enables mutation testing.
allow_active_login_probes: false
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-redirect-uri-lab

OAuth redirect URI mutation probes enabled (pre-auth, GET only).
```

- [ ] **Step 4: Write scope+RoE for oauth-token-substitution-lab**

`programs/local/oauth-token-substitution-lab/scope.md`:
```markdown
---
platform: local
slug: oauth-token-substitution-lab
policy: rate-limited-OK
in_scope:
  - oauth-token-substitution-lab
out_of_scope: []
scope_hash: ""
last_synced: "2026-05-22T00:00:00Z"
---

# oauth-token-substitution-lab fixture

Operator-owned oauth-lab container (SCENARIO=token-sub).
Two scanner-owned users; vulnerable code-binding mode enabled.
```

`programs/local/oauth-token-substitution-lab/roe.md`:
```markdown
---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - oauth-token-substitution-lab
authorized_test_accounts:
  - user_a
  - user_b
special_notes: |
  Two scanner-owned synthetic accounts. Active code-substitution
  test requires allow_oauth_probes=true.
allow_active_login_probes: true
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-token-substitution-lab

Active OAuth token substitution test enabled with two synthetic accounts.
```

- [ ] **Step 5: Write scope+RoE for oauth-account-linking-lab**

`programs/local/oauth-account-linking-lab/scope.md`:
```markdown
---
platform: local
slug: oauth-account-linking-lab
policy: rate-limited-OK
in_scope:
  - oauth-account-linking-lab
out_of_scope: []
scope_hash: ""
last_synced: "2026-05-22T00:00:00Z"
---

# oauth-account-linking-lab fixture

Operator-owned oauth-lab container (SCENARIO=account-link).
Exposes account settings with vulnerable and safe linking flows.
```

`programs/local/oauth-account-linking-lab/roe.md`:
```markdown
---
max_requests_per_second: 30
dos_authorized: false
destructive_payloads_authorized: false
social_engineering_authorized: false
pii_handling: synthetic_data_only
authorized_test_environments:
  - oauth-account-linking-lab
authorized_test_accounts:
  - user_a
  - user_b
special_notes: |
  allow_oauth_probes enables account-linking detection.
  allow_active_login_probes enables two-session state-binding checks.
  Fixture-only mutating tests require allow_mutating_link_tests (future knob).
allow_active_login_probes: true
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-account-linking-lab

OAuth account-linking passive + active fixture checks enabled.
```

- [ ] **Step 6: Add four services to `docker-compose.yml`**

After the `reset-canary` service block, add:

```yaml
  oauth-state-missing:
    image: earnmoney-oauth-lab:dev
    build:
      context: ./fixtures/oauth-lab
      dockerfile: Dockerfile
    environment:
      TZ: Europe/Copenhagen
      PORT: "3000"
      SCENARIO: state-missing
      PUBLIC_BASE_URL: http://oauth-state-missing:3000
    networks: [scanner-net]

  oauth-redirect-uri-lab:
    image: earnmoney-oauth-lab:dev
    environment:
      TZ: Europe/Copenhagen
      PORT: "3000"
      SCENARIO: redirect-uri
      PUBLIC_BASE_URL: http://oauth-redirect-uri-lab:3000
    networks: [scanner-net]

  oauth-token-substitution-lab:
    image: earnmoney-oauth-lab:dev
    environment:
      TZ: Europe/Copenhagen
      PORT: "3000"
      SCENARIO: token-sub
      VULN_MODE: "true"
      PUBLIC_BASE_URL: http://oauth-token-substitution-lab:3000
    networks: [scanner-net]

  oauth-account-linking-lab:
    image: earnmoney-oauth-lab:dev
    environment:
      TZ: Europe/Copenhagen
      PORT: "3000"
      SCENARIO: account-link
      PUBLIC_BASE_URL: http://oauth-account-linking-lab:3000
    networks: [scanner-net]
```

Add env vars to **both** `backend` and `worker` environment blocks:

```yaml
      FIXTURE_OAUTH_STATE_MISSING_URL: ${FIXTURE_OAUTH_STATE_MISSING_URL:-http://oauth-state-missing:3000}
      FIXTURE_OAUTH_REDIRECT_URI_URL: ${FIXTURE_OAUTH_REDIRECT_URI_URL:-http://oauth-redirect-uri-lab:3000}
      FIXTURE_OAUTH_TOKEN_SUB_URL: ${FIXTURE_OAUTH_TOKEN_SUB_URL:-http://oauth-token-substitution-lab:3000}
      FIXTURE_OAUTH_ACCOUNT_LINK_URL: ${FIXTURE_OAUTH_ACCOUNT_LINK_URL:-http://oauth-account-linking-lab:3000}
```

- [ ] **Step 7: Build and verify**

```bash
docker compose build oauth-state-missing
docker compose run --rm oauth-state-missing wget -qO- http://localhost:3000/healthz
# Expected: {"ok":true}
```

- [ ] **Step 8: Commit**

```bash
git add programs/local/oauth-state-missing/ programs/local/oauth-redirect-uri-lab/ \
        programs/local/oauth-token-substitution-lab/ programs/local/oauth-account-linking-lab/ \
        docker-compose.yml
git commit -m "feat(programs): oauth-lab scope+RoE for all 4 scenarios; wire compose services"
```
