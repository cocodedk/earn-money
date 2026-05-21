# Task 06a — Programs scope+RoE: oauth-state-missing and oauth-redirect-uri-lab

Register scope/RoE for the first two oauth-lab scenario services.

**Files:**
- Create: `programs/local/oauth-state-missing/scope.md`
- Create: `programs/local/oauth-state-missing/roe.md`
- Create: `programs/local/oauth-redirect-uri-lab/scope.md`
- Create: `programs/local/oauth-redirect-uri-lab/roe.md`

**Continues in:** [06b-programs-token-sub-account-link.md](06b-programs-token-sub-account-link.md)

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
