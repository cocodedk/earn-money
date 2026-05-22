# Task 06b — Programs scope+RoE: oauth-token-substitution-lab and oauth-account-linking-lab

Register scope/RoE for the remaining two oauth-lab scenario services.

**Files:**
- Create: `programs/local/oauth-token-substitution-lab/scope.md`
- Create: `programs/local/oauth-token-substitution-lab/roe.md`
- Create: `programs/local/oauth-account-linking-lab/scope.md`
- Create: `programs/local/oauth-account-linking-lab/roe.md`

**Continues from:** [06a-programs-state-missing-redirect.md](06a-programs-state-missing-redirect.md)
**Continues in:** [06c-compose-wiring.md](06c-compose-wiring.md)

---

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
  Fixture-only mutating link probes are allowed only for this local fixture
  with scanner-owned synthetic accounts.
allow_active_login_probes: true
allow_password_reset_probes: false
allow_mfa_probes: false
allow_oauth_probes: true
allow_registration_probes: false
---

# RoE — local/oauth-account-linking-lab

OAuth account-linking passive + active fixture checks enabled.
```
