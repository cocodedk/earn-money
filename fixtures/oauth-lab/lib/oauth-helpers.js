// lib/oauth-helpers.js — shared OAuth plumbing; no intentional vulns here.
'use strict';
const crypto = require('crypto');

// Known test clients. Scenarios add entries; helpers never validate policy.
const _clients = new Map();

function registerClient(id, { redirectUris = [], allowSubstitution = false } = {}) {
  _clients.set(id, { redirectUris, allowSubstitution });
}

function getClient(id) { return _clients.get(id) ?? null; }

function clearClients() { _clients.clear(); }

function generateState() { return crypto.randomBytes(12).toString('hex'); }

function generateCode() { return 'code-' + crypto.randomBytes(8).toString('hex'); }

function buildDiscoveryDoc(baseUrl) {
  return {
    issuer: baseUrl,
    authorization_endpoint: `${baseUrl}/oauth/authorize`,
    token_endpoint: `${baseUrl}/oauth/token`,
    response_types_supported: ['code'],
    grant_types_supported: ['authorization_code'],
  };
}

function parseRedirectUri(raw) {
  try { return new URL(raw); } catch { return null; }
}

function originOf(urlOrStr) {
  const u = typeof urlOrStr === 'string' ? parseRedirectUri(urlOrStr) : urlOrStr;
  return u ? u.origin : null;
}

module.exports = {
  registerClient, getClient, clearClients,
  generateState, generateCode,
  buildDiscoveryDoc, parseRedirectUri, originOf,
};
