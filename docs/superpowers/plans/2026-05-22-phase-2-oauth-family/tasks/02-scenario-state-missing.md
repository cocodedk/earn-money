# Task 02 — Scenario: state-missing (for stub 2.15)

Create the `state-missing` scenario fixture. Exposes two deterministic
flows: a vulnerable login that redirects to an auth URL without `state`,
and a safe login that includes `state`.

**Files:**
- Create: `fixtures/oauth-lab/scenarios/state-missing.js`

**Depends on:** Task 01 (server.js + lib/)

---

- [ ] **Step 1: Write `scenarios/state-missing.js`** (≤200 lines)

```js
// scenarios/state-missing.js
// Stub 2.15 fixture: two SSO entry points — one omits `state`, one includes it.
//
// Intentional vulnerability:
//   GET /auth/example  →  302 Location: /oauth/authorize?client_id=...&response_type=code
//                         ↳ no `state` parameter
//
// Safe flow:
//   GET /auth/safe     →  302 Location: /oauth/authorize?...&state=<random>
//
// Callback paths accept code-shaped requests to let the stub probe
// whether missing-state is rejected server-side.
'use strict';
const { Router } = require('express');
const { generateState, generateCode, buildDiscoveryDoc } = require('../lib/oauth-helpers');

const BASE_URL = process.env.PUBLIC_BASE_URL || 'http://oauth-state-missing:3000';
const CLIENT_ID = 'test-client';
const REDIRECT_URI = `${BASE_URL}/auth/example/callback`;

const router = Router();

// OIDC discovery
router.get('/.well-known/openid-configuration', (_req, res) => {
  res.json(buildDiscoveryDoc(BASE_URL));
});

// Login page — contains two SSO links
router.get('/login', (_req, res) => {
  res.send(`<!doctype html><html><body>
    <a href="/auth/example">Continue with Example IdP</a>
    <a href="/auth/safe">Continue with Safe IdP</a>
  </body></html>`);
});

// Vulnerable entry: redirects to auth URL WITHOUT state
router.get('/auth/example', (_req, res) => {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: 'code',
    scope: 'openid profile',
  });
  res.redirect(302, `/oauth/authorize?${params}`);
});

// Safe entry: redirects to auth URL WITH state
router.get('/auth/safe', (_req, res) => {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: `${BASE_URL}/auth/safe/callback`,
    response_type: 'code',
    scope: 'openid profile',
    state: generateState(),
  });
  res.redirect(302, `/oauth/authorize?${params}`);
});

// Authorization endpoint — does not perform real auth; just issues a code
router.get('/oauth/authorize', (req, res) => {
  const code = generateCode();
  const redirectUri = req.query.redirect_uri || REDIRECT_URI;
  const state = req.query.state;
  const dest = new URL(redirectUri);
  dest.searchParams.set('code', code);
  if (state) dest.searchParams.set('state', state);
  res.redirect(302, dest.toString());
});

// Vulnerable callback — accepts the callback without requiring state
router.get('/auth/example/callback', (req, res) => {
  // Intentionally does NOT reject missing state
  const code = req.query.code;
  if (!code) return res.status(400).json({ error: 'missing_code' });
  res.json({ ok: true, code_received: true, state_checked: false });
});

// Safe callback — rejects requests without state
router.get('/auth/safe/callback', (req, res) => {
  const { code, state } = req.query;
  if (!code) return res.status(400).json({ error: 'missing_code' });
  if (!state) return res.status(400).json({ error: 'missing_state', error_description: 'state parameter is required' });
  res.json({ ok: true, code_received: true, state_checked: true });
});

module.exports = router;
```

- [ ] **Step 2: Smoke-test the scenario locally**

```bash
cd fixtures/oauth-lab
SCENARIO=state-missing PUBLIC_BASE_URL=http://localhost:3000 node server.js &
sleep 1

# Fixture info
curl -s http://localhost:3000/fixture-info
# Expected: {"scenario":"state-missing"}

# Vulnerable flow — authorize URL must NOT contain state
curl -s -I http://localhost:3000/auth/example | grep -i location
# Expected: /oauth/authorize?...  (no state= in params)

# Safe flow — authorize URL MUST contain state
curl -s -I http://localhost:3000/auth/safe | grep -i location
# Expected: /oauth/authorize?...&state=<hex>

# Reset endpoint
curl -s -X POST http://localhost:3000/reset
# Expected: {"ok":true,...}

kill %1
```

- [ ] **Step 3: Commit**

```bash
git add fixtures/oauth-lab/scenarios/state-missing.js
git commit -m "feat(fixture): oauth-lab state-missing scenario for stub 2.15"
```
