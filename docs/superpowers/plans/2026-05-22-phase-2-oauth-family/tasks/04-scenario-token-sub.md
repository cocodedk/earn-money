# Task 04 — Scenario: token-sub (for stub 2.16)

Create the `token-sub` scenario fixture. Two users (user_a, user_b),
two auth flow modes (fixed/vulnerable), `/me` identity endpoint.

**Files:**
- Create: `fixtures/oauth-lab/scenarios/token-sub.js`

**Depends on:** Task 01

---

- [ ] **Step 1: Write `scenarios/token-sub.js`** (≤200 lines)

```js
// scenarios/token-sub.js
// Stub 2.16 fixture: two-user OAuth flow with vulnerable and safe
// code-binding modes.
//
// Intentional vulnerability (mode=vulnerable-code-substitution):
//   Authorization code from user_a is accepted in user_b callback.
//   POST /oauth/callback with a code captured for user_a + session of user_b
//   → server accepts and returns user_a identity.
//
// Safe mode (mode=fixed-code-binding):
//   Code is bound to session; cross-session substitution → 400 invalid_grant.
//
// Env var: VULN_MODE=true enables vulnerable code binding.
'use strict';
const { Router } = require('express');
const session = require('../lib/session');
const { generateCode, generateState } = require('../lib/oauth-helpers');

const VULN_MODE = process.env.VULN_MODE === 'true';

// Synthetic users — fixed identities for scanner-owned test accounts
const USERS = {
  user_a: { password: 'pass-a', marker: 'user_a_marker' },
  user_b: { password: 'pass-b', marker: 'user_b_marker' },
};

// code → { userId, sessionToken }
const _codes = new Map();

const router = Router();

router.post('/reset', (_req, res) => {
  session.reset();
  _codes.clear();
  res.json({ ok: true });
});

// POST /login — returns session token
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = USERS[username];
  if (!user || user.password !== password) {
    return res.status(401).json({ error: 'invalid_credentials' });
  }
  const token = session.create({ userId: username });
  res.json({ token, userId: username });
});

// GET /oauth/authorize — issues code bound to current session
router.get('/oauth/authorize', (req, res) => {
  const { redirect_uri, state } = req.query;
  const token = req.headers['x-session-token'];
  const sess = session.get(token);
  if (!sess) return res.status(401).json({ error: 'unauthenticated' });

  const code = generateCode();
  _codes.set(code, { userId: sess.userId, sessionToken: token });

  const dest = new URL(redirect_uri || 'http://localhost/callback');
  dest.searchParams.set('code', code);
  if (state) dest.searchParams.set('state', state);
  res.redirect(302, dest.toString());
});

// POST /oauth/callback — exchange code; validates session binding in safe mode
router.post('/oauth/callback', (req, res) => {
  const { code } = req.body;
  const token = req.headers['x-session-token'];
  const sess = session.get(token);
  const codeData = _codes.get(code);

  if (!codeData) return res.status(400).json({ error: 'invalid_grant', error_description: 'code not found' });
  _codes.delete(code); // one-time use

  if (!VULN_MODE && codeData.sessionToken !== token) {
    // SAFE: code must belong to the current session
    return res.status(400).json({ error: 'invalid_grant', error_description: 'code bound to different session' });
  }

  // Vulnerable mode (or safe mode where same session) — issue access
  const user = USERS[codeData.userId];
  const accessToken = session.create({ userId: codeData.userId, kind: 'access' });
  res.json({ access_token: accessToken, marker: user.marker, userId: codeData.userId });
});

// GET /me — returns identity marker for current session
router.get('/me', (req, res) => {
  const token = req.headers['x-session-token'] || req.headers.authorization?.replace('Bearer ', '');
  const sess = session.get(token);
  if (!sess) return res.status(401).json({ error: 'unauthenticated' });
  const user = USERS[sess.userId];
  res.json({ userId: sess.userId, marker: user?.marker ?? 'unknown' });
});

module.exports = router;
```

- [ ] **Step 2: Smoke-test**

```bash
cd fixtures/oauth-lab
SCENARIO=token-sub VULN_MODE=true PUBLIC_BASE_URL=http://localhost:3000 node server.js &
sleep 1

# Login as user_a
TOK_A=$(curl -s -X POST http://localhost:3000/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"user_a","password":"pass-a"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Authorize as user_a to get code
CODE_A=$(curl -sv -H "X-Session-Token: $TOK_A" \
  "http://localhost:3000/oauth/authorize?redirect_uri=http://localhost/cb&state=abc" \
  2>&1 | grep -i location | sed 's/.*code=\([^&]*\).*/\1/')

echo "Code for user_a: $CODE_A"

# Login as user_b separately
TOK_B=$(curl -s -X POST http://localhost:3000/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"user_b","password":"pass-b"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Substitute user_a code in user_b's callback (VULN_MODE=true — must succeed)
curl -s -X POST http://localhost:3000/oauth/callback \
  -H "X-Session-Token: $TOK_B" \
  -H 'Content-Type: application/json' \
  -d "{\"code\":\"$CODE_A\"}"
# Expected in VULN_MODE: {"access_token":...,"marker":"user_a_marker","userId":"user_a"}
# (wrong identity returned — confirmed vulnerability)

kill %1
```

- [ ] **Step 3: Commit**

```bash
git add fixtures/oauth-lab/scenarios/token-sub.js
git commit -m "feat(fixture): oauth-lab token-sub scenario for stub 2.16"
```
