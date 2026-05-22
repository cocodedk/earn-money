# Task 03 — Scenario: redirect-uri (for stub 2.14)

Create the `redirect-uri` scenario fixture. Exposes five authorization
endpoint variants covering strict rejection, loose matching bugs, a
foreign-origin redirect, and a preserves-invalid pattern.

**Files:**
- Create: `fixtures/oauth-lab/scenarios/redirect-uri.js`

**Depends on:** Task 01

---

- [ ] **Step 1: Write `scenarios/redirect-uri.js`** (≤200 lines)

```js
// scenarios/redirect-uri.js
// Stub 2.14 fixture: authorization server with intentional redirect_uri
// validation weaknesses.
//
// Intentional vulnerabilities:
//   /oauth/authorize/loose-host-prefix  — accepts host-suffix tricks
//   /oauth/authorize/loose-path-prefix  — accepts path-prefix tricks
//   /oauth/authorize/foreign-origin     — redirects to any origin
//   /oauth/authorize/preserves-invalid  — returns login HTML with
//                                         redirect_uri in hidden field
//
// Safe endpoint:
//   /oauth/authorize/strict             — rejects unknown redirect URIs
'use strict';
const { Router } = require('express');
const { buildDiscoveryDoc, generateCode, generateState } = require('../lib/oauth-helpers');

const BASE_URL = process.env.PUBLIC_BASE_URL || 'http://oauth-redirect-uri-lab:3000';
const VALID_REDIRECT = 'https://app.example.test/oauth/callback';
const SCANNER_ORIGIN = 'https://scanner.invalid';
const CLIENT_ID = 'test-client';

const router = Router();

router.get('/.well-known/openid-configuration', (_req, res) => {
  res.json({
    ...buildDiscoveryDoc(BASE_URL),
    authorization_endpoint: `${BASE_URL}/oauth/authorize/strict`,
    // Fixture extension: scanner runners must probe these variants too.
    authorization_endpoint_variants: [
      `${BASE_URL}/oauth/authorize/loose-host-prefix`,
      `${BASE_URL}/oauth/authorize/loose-path-prefix`,
      `${BASE_URL}/oauth/authorize/foreign-origin`,
      `${BASE_URL}/oauth/authorize/preserves-invalid`,
    ],
  });
});

// Login page with SSO link using the strict endpoint
router.get('/login', (_req, res) => {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: VALID_REDIRECT,
    response_type: 'code',
    state: generateState(),
  });
  res.send(`<!doctype html><html><body>
    <a href="/oauth/authorize/strict?${params}">Sign in</a>
  </body></html>`);
});

function isValidRedirect(uri) {
  return uri === VALID_REDIRECT;
}

function isLooseHostMatch(uri) {
  // Simulate prefix/suffix host vulnerability: accepts if VALID_REDIRECT host
  // appears anywhere in the redirect URI host (bad substring match).
  try {
    const u = new URL(uri);
    const valid = new URL(VALID_REDIRECT);
    return u.hostname.includes(valid.hostname) || valid.hostname.includes(u.hostname);
  } catch { return false; }
}

// STRICT — correctly rejects unknown redirect URIs
router.get('/oauth/authorize/strict', (req, res) => {
  const { redirect_uri, client_id } = req.query;
  if (!client_id || !redirect_uri || !isValidRedirect(redirect_uri)) {
    return res.status(400).json({
      error: 'invalid_redirect_uri',
      error_description: 'redirect_uri is not registered for this client',
    });
  }
  const code = generateCode();
  const dest = new URL(redirect_uri);
  dest.searchParams.set('code', code);
  if (req.query.state) dest.searchParams.set('state', req.query.state);
  res.redirect(302, dest.toString());
});

// LOOSE-HOST-PREFIX — vulnerable: accepts if trusted host is a substring
router.get('/oauth/authorize/loose-host-prefix', (req, res) => {
  const { redirect_uri } = req.query;
  if (!redirect_uri || !isLooseHostMatch(redirect_uri)) {
    return res.status(400).json({ error: 'invalid_redirect_uri' });
  }
  const code = generateCode();
  const dest = new URL(redirect_uri);
  dest.searchParams.set('code', code);
  res.redirect(302, dest.toString());
});

// LOOSE-PATH-PREFIX — vulnerable: accepts if path starts with valid path
router.get('/oauth/authorize/loose-path-prefix', (req, res) => {
  const { redirect_uri } = req.query;
  try {
    const u = new URL(redirect_uri);
    const valid = new URL(VALID_REDIRECT);
    if (u.hostname === valid.hostname && u.pathname.startsWith('/oauth/callback')) {
      const dest = new URL(redirect_uri);
      dest.searchParams.set('code', generateCode());
      return res.redirect(302, dest.toString());
    }
  } catch {}
  res.status(400).json({ error: 'invalid_redirect_uri' });
});

// FOREIGN-ORIGIN — vulnerable: redirects to any provided origin
router.get('/oauth/authorize/foreign-origin', (req, res) => {
  const { redirect_uri } = req.query;
  if (!redirect_uri) return res.status(400).json({ error: 'missing_redirect_uri' });
  let dest;
  try { dest = new URL(redirect_uri); } catch { return res.status(400).json({ error: 'invalid_redirect_uri' }); }
  dest.searchParams.set('code', generateCode());
  res.redirect(302, dest.toString());
});

// PRESERVES-INVALID — returns login HTML preserving the redirect_uri in a hidden field
router.get('/oauth/authorize/preserves-invalid', (req, res) => {
  const { redirect_uri = '', client_id = '', state = '' } = req.query;
  res.send(`<!doctype html><html><body>
    <form method="post" action="/oauth/authorize/preserves-invalid/submit">
      <input type="hidden" name="redirect_uri" value="${redirect_uri}">
      <input type="hidden" name="client_id" value="${client_id}">
      <input type="hidden" name="state" value="${state}">
      <input type="text" name="username" placeholder="Username">
      <input type="password" name="password" placeholder="Password">
      <button type="submit">Sign in</button>
    </form>
  </body></html>`);
});

module.exports = router;
```

- [ ] **Step 2: Smoke-test**

```bash
cd fixtures/oauth-lab
SCENARIO=redirect-uri PUBLIC_BASE_URL=http://localhost:3000 node server.js &
sleep 1

# Strict rejects foreign origin
curl -s "http://localhost:3000/oauth/authorize/strict?client_id=test-client&redirect_uri=https://scanner.invalid/cb&response_type=code&state=abc"
# Expected: 400 {"error":"invalid_redirect_uri",...}

# Foreign-origin endpoint redirects to scanner.invalid
curl -sI "http://localhost:3000/oauth/authorize/foreign-origin?client_id=test-client&redirect_uri=https://scanner.invalid/cb&response_type=code"
# Expected: 302 Location: https://scanner.invalid/cb?code=...

# OIDC discovery
curl -s http://localhost:3000/.well-known/openid-configuration | python3 -m json.tool
# Expected: JSON with authorization_endpoint and authorization_endpoint_variants

kill %1
```

- [ ] **Step 3: Commit**

```bash
git add fixtures/oauth-lab/scenarios/redirect-uri.js
git commit -m "feat(fixture): oauth-lab redirect-uri scenario for stub 2.14"
```
