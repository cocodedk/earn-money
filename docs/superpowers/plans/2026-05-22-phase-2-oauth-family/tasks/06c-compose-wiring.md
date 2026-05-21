# Task 06c — docker-compose service definitions, fixture program wiring, commit

Add the four oauth-lab compose services, wire env vars to backend and worker, verify, and commit.

**Files:**
- Modify: `docker-compose.yml`

**Continues from:** [06b-programs-token-sub-account-link.md](06b-programs-token-sub-account-link.md)

---

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
    build:
      context: ./fixtures/oauth-lab
      dockerfile: Dockerfile
    environment:
      TZ: Europe/Copenhagen
      PORT: "3000"
      SCENARIO: redirect-uri
      PUBLIC_BASE_URL: http://oauth-redirect-uri-lab:3000
    networks: [scanner-net]

  oauth-token-substitution-lab:
    image: earnmoney-oauth-lab:dev
    build:
      context: ./fixtures/oauth-lab
      dockerfile: Dockerfile
    environment:
      TZ: Europe/Copenhagen
      PORT: "3000"
      SCENARIO: token-sub
      VULN_MODE: "true"
      PUBLIC_BASE_URL: http://oauth-token-substitution-lab:3000
    networks: [scanner-net]

  oauth-account-linking-lab:
    image: earnmoney-oauth-lab:dev
    build:
      context: ./fixtures/oauth-lab
      dockerfile: Dockerfile
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
