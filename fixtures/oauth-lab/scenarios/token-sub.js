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
const BASE_URL = process.env.PUBLIC_BASE_URL || 'http://oauth-token-substitution-lab:3000';

// Synthetic users — fixed identities for scanner-owned test accounts
const USERS = {
  user_a: { password: 'pass-a', marker: 'user_a_marker' },
  user_b: { password: 'pass-b', marker: 'user_b_marker' },
};

// code → { userId, sessionToken }
const _codes = new Map();

const router = Router();

// reset() is called by server.js's /reset handler (see task 01).
// Do NOT add router.post('/reset') here — server.js registers that first and it would shadow this.

// GET /login — passive discovery surface with OAuth-looking link markup.
// The real flow still requires POST /login first to obtain X-Session-Token.
router.get('/login', (_req, res) => {
  const params = new URLSearchParams({
    client_id: 'token-sub-client',
    redirect_uri: `${BASE_URL}/oauth/callback`,
    response_type: 'code',
    state: generateState(),
  });
  res.send(`<!doctype html><html><body>
    <a href="/oauth/authorize?${params}">Continue with OAuth</a>
  </body></html>`);
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

  let dest;
  try { dest = new URL(redirect_uri || `${BASE_URL}/oauth/callback`); }
  catch { return res.status(400).json({ error: 'invalid_redirect_uri' }); }
  dest.searchParams.set('code', code);
  if (state) dest.searchParams.set('state', state);
  res.redirect(302, dest.toString());
});

// POST /oauth/callback — exchange code; validates session binding in safe mode
router.post('/oauth/callback', (req, res) => {
  const { code } = req.body;
  const token = req.headers['x-session-token'];
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

// Export both router and reset so server.js can clear _codes on POST /reset
module.exports = { router, reset() { _codes.clear(); } };
