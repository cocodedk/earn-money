# Task 05 — Scenario: account-link (for stub 2.17)

Create the `account-link` scenario fixture. Exposes account settings with
linking UI, vulnerable and safe link flows.

**Files:**
- Create: `fixtures/oauth-lab/scenarios/account-link.js`

**Depends on:** Task 01

---

- [ ] **Step 1: Write `scenarios/account-link.js`** (≤200 lines)

```js
// scenarios/account-link.js
// Stub 2.17 fixture: account-linking flows with intentional weaknesses.
//
// Intentional vulnerabilities:
//   GET /settings/connections/link/mock  — state-changing GET (link_over_get)
//   GET /auth/link/start                 — omits `state` (missing_state)
//   POST /auth/link/callback             — no CSRF token required (missing_csrf_on_link)
//   GET /auth/link/callback-client-id    — accepts client-controlled provider_user_id
//
// Safe flows:
//   POST /auth/link/start-safe           — uses per-session state
//   POST /auth/link/callback-safe        — validates state, requires code
'use strict';
const { Router } = require('express');
const session = require('../lib/session');
const { generateState, generateCode } = require('../lib/oauth-helpers');

const BASE_URL = process.env.PUBLIC_BASE_URL || 'http://oauth-account-linking-lab:3000';

function makeUsers() {
  return {
    user_a: { password: 'pass-a', linkedProviders: [] },
    user_b: { password: 'pass-b', linkedProviders: [] },
  };
}

let USERS = makeUsers();

// session_token → pending link state
const _linkStates = new Map();

const router = Router();

// Auth
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = USERS[username];
  if (!user || user.password !== password) {
    return res.status(401).json({ error: 'invalid_credentials' });
  }
  const token = session.create({ userId: username });
  res.json({ token, userId: username });
});

function requireSession(req, res, next) {
  const token = req.headers['x-session-token'];
  const sess = session.get(token);
  if (!sess) return res.status(401).json({ error: 'unauthenticated' });
  req.sess = sess;
  req.sessionToken = token;
  next();
}

// Account connections page
router.get('/settings/connections', requireSession, (req, res) => {
  const user = USERS[req.sess.userId];
  res.json({ userId: req.sess.userId, linkedProviders: user.linkedProviders });
});

// VULNERABLE: state-changing action over GET (link_over_get)
router.get('/settings/connections/link/mock', requireSession, (req, res) => {
  const user = USERS[req.sess.userId];
  user.linkedProviders.push({ provider: 'mock', providerUserId: 'fixture-provider-subject-a' });
  res.json({ ok: true, linked: true, method_used: 'GET' });
});

// VULNERABLE: link start — omits state (missing_state)
router.get('/auth/link/start', requireSession, (req, res) => {
  const params = new URLSearchParams({
    client_id: 'link-client',
    redirect_uri: `${BASE_URL}/auth/link/callback`,
    response_type: 'code',
    // intentionally omits state
  });
  res.redirect(302, `/oauth/authorize-mock?${params}`);
});

// Mock auth endpoint — issues a code for linking
router.get('/oauth/authorize-mock', (req, res) => {
  const { redirect_uri, state } = req.query;
  let dest;
  try { dest = new URL(redirect_uri || `${BASE_URL}/auth/link/callback`); }
  catch { return res.status(400).json({ error: 'invalid_redirect_uri' }); }
  dest.searchParams.set('code', generateCode());
  if (state) dest.searchParams.set('state', state);
  res.redirect(302, dest.toString());
});

// VULNERABLE: callback — no CSRF token, no state validation
router.post('/auth/link/callback', requireSession, (req, res) => {
  const { code, provider_user_id } = req.body;
  const userId = provider_user_id || `fixture-provider-from-code-${code}`;
  USERS[req.sess.userId].linkedProviders.push({ provider: 'mock', providerUserId: userId });
  res.json({ ok: true, linked: true, csrf_checked: false, state_checked: false });
});

// VULNERABLE: callback accepts client-controlled identity (callback_accepts_client_identity)
router.get('/auth/link/callback-client-id', requireSession, (req, res) => {
  const { provider_user_id } = req.query;
  if (provider_user_id) {
    USERS[req.sess.userId].linkedProviders.push({ provider: 'mock', providerUserId: provider_user_id });
    return res.json({ ok: true, linked: true, identity_source: 'client_parameter' });
  }
  res.status(400).json({ error: 'missing_provider_user_id' });
});

// SAFE: link start — uses per-session state
router.post('/auth/link/start-safe', requireSession, (req, res) => {
  const state = generateState();
  _linkStates.set(req.sessionToken, state);
  const params = new URLSearchParams({
    client_id: 'link-client',
    redirect_uri: `${BASE_URL}/auth/link/callback-safe`,
    response_type: 'code',
    state,
  });
  res.redirect(302, `/oauth/authorize-mock?${params}`);
});

// SAFE: callback — validates state, requires code
router.post('/auth/link/callback-safe', requireSession, (req, res) => {
  const { code, state, _csrf } = req.body;
  const expected = _linkStates.get(req.sessionToken);
  if (!_csrf) return res.status(400).json({ error: 'missing_csrf' });
  if (!state || state !== expected) return res.status(400).json({ error: 'invalid_state' });
  if (!code) return res.status(400).json({ error: 'missing_code' });
  _linkStates.delete(req.sessionToken);
  USERS[req.sess.userId].linkedProviders.push({ provider: 'mock', providerUserId: 'fixture-provider-safe' });
  res.json({ ok: true, linked: true, csrf_checked: true, state_checked: true });
});

// Fixture introspection — scanner-only endpoint showing connection state
router.get('/__fixture/account-state', requireSession, (req, res) => {
  res.json({ userId: req.sess.userId, linkedProviders: USERS[req.sess.userId].linkedProviders });
});

function reset() {
  USERS = makeUsers();
  _linkStates.clear();
}

module.exports = { router, reset };
```

- [ ] **Step 2: Smoke-test key paths**

```bash
cd fixtures/oauth-lab
SCENARIO=account-link PUBLIC_BASE_URL=http://localhost:3000 node server.js &
sleep 1

# Login
TOK=$(curl -s -X POST http://localhost:3000/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"user_a","password":"pass-a"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Vulnerable GET link
curl -s -H "X-Session-Token: $TOK" http://localhost:3000/settings/connections/link/mock
# Expected: {"ok":true,"linked":true,"method_used":"GET"}

# State check — missing state on link start
curl -sv -H "X-Session-Token: $TOK" http://localhost:3000/auth/link/start 2>&1 | grep -i location
# Expected: /oauth/authorize-mock?... (no state= param)

# Account state endpoint
curl -s -H "X-Session-Token: $TOK" http://localhost:3000/__fixture/account-state
# Expected: linkedProviders shows the mock link

# Reset clears sessions and linked provider state
curl -s -X POST http://localhost:3000/reset
# Expected: {"ok":true,...}

kill %1
```

- [ ] **Step 3: Commit**

```bash
git add fixtures/oauth-lab/scenarios/account-link.js
git commit -m "feat(fixture): oauth-lab account-link scenario for stub 2.17"
```
