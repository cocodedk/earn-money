// lib/session.js — in-memory session store; wiped by POST /reset.
// SAFETY: in-memory only; never deploy outside the fixture network.
'use strict';
const crypto = require('crypto');

const _sessions = new Map();

function create(data = {}) {
  const token = crypto.randomBytes(16).toString('hex');
  _sessions.set(token, { ...data, createdAt: Date.now() });
  return token;
}

function get(token) { return _sessions.get(token) ?? null; }

function set(token, data) {
  if (!_sessions.has(token)) return false;
  _sessions.set(token, { ..._sessions.get(token), ...data });
  return true;
}

function destroy(token) { _sessions.delete(token); }

function reset() { _sessions.clear(); }

function size() { return _sessions.size; }

module.exports = { create, get, set, destroy, reset, size };
