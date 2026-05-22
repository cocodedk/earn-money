// scenarios/invitation-abuse.js
// Stub 2.21 fixture: invitation flows with intentional weaknesses.
//
// VULNERABLE flows:
//   GET /fixture/invitations/:token        — leaks workspace/role/inviter to unauthenticated
//   POST /fixture/invitations/:token/accept — accepts any authenticated user (not bound to recipient)
//   POST /fixture/invitations/:token/accept — reusable (no single-use enforcement)
//
// SAFE flows:
//   POST /fixture/invitations/:token/accept-secure — bound to intended recipient, single-use
'use strict';
const { Router } = require('express');
const session = require('../lib/session');

const FIXTURE_TOKEN = 'fixture-invite-token-001';
const FIXTURE_TENANT = 'acme-test';
const FIXTURE_ROLE = 'member';
const FIXTURE_INVITER = 'inviter@example.test';
const FIXTURE_INTENDED_RECIPIENT = 'recipient@example.test';

function makeState() {
  return {
    users: {
      inviter: { password: 'pass-inviter', role: 'editor', tenant: FIXTURE_TENANT, email: 'inviter@example.test' },
      recipient: { password: 'pass-recipient', role: null, tenant: null, email: FIXTURE_INTENDED_RECIPIENT },
      unrelated: { password: 'pass-unrelated', role: null, tenant: null, email: 'unrelated@example.test' },
    },
    invites: new Map([
      [FIXTURE_TOKEN, {
        token: FIXTURE_TOKEN,
        workspace: FIXTURE_TENANT,
        role: FIXTURE_ROLE,
        invited_by: FIXTURE_INVITER,
        intended_recipient: FIXTURE_INTENDED_RECIPIENT,
        accepted_by: [],
      }],
    ]),
    members: new Set(['inviter']),
  };
}

let STATE = makeState();

const router = Router();

router.post('/login', (req, res) => {
  const { username, password } = req.body;
  const user = STATE.users[username];
  if (!user || user.password !== password) {
    return res.status(401).json({ error: 'invalid_credentials' });
  }
  const token = session.create({ userId: username });
  res.json({ token, userId: username });
});

function requireSession(req, res, next) {
  const t = req.headers['x-session-token'];
  const sess = session.get(t);
  if (!sess) return res.status(401).json({ error: 'unauthenticated' });
  req.sess = sess;
  next();
}

// Surface discovery (authenticated)
router.get('/fixture/invitations', requireSession, (req, res) => {
  res.json({
    invitations: [{ token: FIXTURE_TOKEN, workspace: FIXTURE_TENANT, role: FIXTURE_ROLE }],
    invite_creation_url: '/fixture/invitations',
  });
});

// VULNERABLE: unauthenticated GET leaks workspace/role/inviter
router.get('/fixture/invitations/:token', (req, res) => {
  const inv = STATE.invites.get(req.params.token);
  if (!inv) return res.status(404).json({ error: 'not_found' });
  res.json({
    workspace: inv.workspace,
    role: inv.role,
    invited_by: inv.invited_by,
    token: req.params.token,
  });
});

// VULNERABLE: accepts any authenticated user (recipient_not_bound + reusable)
router.post('/fixture/invitations/:token/accept', requireSession, (req, res) => {
  const inv = STATE.invites.get(req.params.token);
  if (!inv) return res.status(404).json({ error: 'not_found' });
  const userId = req.sess.userId;
  inv.accepted_by.push(userId);
  STATE.members.add(userId);
  STATE.users[userId].role = inv.role;
  STATE.users[userId].tenant = inv.workspace;
  res.json({ status: 'accepted', member_created: true, workspace: inv.workspace, role: inv.role });
});

// SAFE: single-use, bound to intended recipient
router.post('/fixture/invitations/:token/accept-secure', requireSession, (req, res) => {
  const inv = STATE.invites.get(req.params.token);
  if (!inv) return res.status(404).json({ error: 'not_found' });
  const userId = req.sess.userId;
  const user = STATE.users[userId];
  if (!user || user.email !== inv.intended_recipient) {
    return res.status(403).json({ error: 'invite_bound_to_recipient' });
  }
  if (inv.accepted_by.length > 0) {
    return res.status(410).json({ error: 'invite_already_used' });
  }
  inv.accepted_by.push(userId);
  STATE.members.add(userId);
  STATE.users[userId].role = inv.role;
  STATE.users[userId].tenant = inv.workspace;
  res.json({ status: 'accepted', member_created: true });
});

router.get('/fixture/members', requireSession, (req, res) => {
  res.json({ members: Array.from(STATE.members), workspace: FIXTURE_TENANT });
});

function reset() { STATE = makeState(); }

module.exports = { router, reset };
