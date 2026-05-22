// scenarios/tenant-org-join.js
// Stub 2.22 fixture: tenant/org join flows with intentional weaknesses.
//
// VULNERABLE flows:
//   POST /api/workspaces/acme/join     — any authenticated user can join without invite (UNAUTHORIZED)
//
// SAFE flows:
//   POST /api/workspaces/acme/join-secure  — requires valid invite token
//   GET  /signup, POST /signup             — registration with optional workspace field
'use strict';
const { Router } = require('express');
const session = require('../lib/session');

const TENANT_SLUG = 'acme';
const TENANT_NAME = 'Acme Test Tenant';

function makeState() {
  return {
    users: {
      owner: { password: 'pass-owner', email: 'owner@example.test', tenant: TENANT_SLUG },
      member: { password: 'pass-member', email: 'member@example.test', tenant: TENANT_SLUG },
      outside: { password: 'pass-outside', email: 'outside@example.test', tenant: null },
    },
    tenants: {
      [TENANT_SLUG]: { name: TENANT_NAME, members: new Set(['owner', 'member']) },
    },
    invites: new Map([
      ['valid-invite-token', {
        tenant: TENANT_SLUG, role: 'member', single_use: true, used: false,
      }],
    ]),
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

// Surface discovery: workspace dashboard
router.get('/workspace/:slug', requireSession, (req, res) => {
  const tenant = STATE.tenants[req.params.slug];
  if (!tenant) return res.status(404).json({ error: 'not_found' });
  const isMember = tenant.members.has(req.sess.userId);
  res.json({
    workspace: req.params.slug,
    name: tenant.name,
    is_member: isMember,
    join_url: `/api/workspaces/${req.params.slug}/join`,
  });
});

router.get('/workspace/:slug/members', requireSession, (req, res) => {
  const tenant = STATE.tenants[req.params.slug];
  if (!tenant) return res.status(404).json({ error: 'not_found' });
  res.json({ workspace: req.params.slug, members: Array.from(tenant.members) });
});

// VULNERABLE: any authenticated user can join without invite
router.post('/api/workspaces/:slug/join', requireSession, (req, res) => {
  const tenant = STATE.tenants[req.params.slug];
  if (!tenant) return res.status(404).json({ error: 'not_found' });
  const userId = req.sess.userId;
  tenant.members.add(userId);
  STATE.users[userId].tenant = req.params.slug;
  res.json({
    TENANT_ORG_JOIN_ABUSE_VULNERABLE: true,
    TENANT_ORG_JOIN_ABUSE_JOINED_EXISTING_TENANT: true,
    workspace_member: true,
    workspace: req.params.slug,
  });
});

// SAFE: requires valid invite token
router.post('/api/workspaces/:slug/join-secure', requireSession, (req, res) => {
  const { invite_token } = req.body;
  if (!invite_token) {
    return res.status(403).json({ TENANT_ORG_JOIN_ABUSE_INVITE_REQUIRED: true, error: 'invite_required' });
  }
  const invite = STATE.invites.get(invite_token);
  if (!invite || invite.tenant !== req.params.slug) {
    return res.status(403).json({ TENANT_ORG_JOIN_ABUSE_INVITE_REQUIRED: true, error: 'invalid_invite' });
  }
  if (invite.single_use && invite.used) {
    return res.status(410).json({ error: 'invite_already_used' });
  }
  invite.used = true;
  const tenant = STATE.tenants[req.params.slug];
  const userId = req.sess.userId;
  tenant.members.add(userId);
  STATE.users[userId].tenant = req.params.slug;
  res.json({ workspace_member: true, workspace: req.params.slug });
});

// Signup (shows tenant field surface)
router.get('/signup', (_req, res) => {
  res.json({ form: 'signup', workspace_field: true, join_url: '/api/workspaces/{slug}/join' });
});

function reset() { STATE = makeState(); }

module.exports = { router, reset };
