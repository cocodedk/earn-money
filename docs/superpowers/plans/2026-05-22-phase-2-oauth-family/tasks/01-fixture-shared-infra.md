# Task 01 — oauth-lab fixture: shared infra

Create `fixtures/oauth-lab/` with the shared plumbing that all four
scenario files depend on.

**Files:**
- Create: `fixtures/oauth-lab/package.json`
- Create: `fixtures/oauth-lab/Dockerfile`
- Create: `fixtures/oauth-lab/lib/session.js`
- Create: `fixtures/oauth-lab/lib/oauth-helpers.js`
- Create: `fixtures/oauth-lab/server.js`

---

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "oauth-lab",
  "version": "0.1.0",
  "description": "Intentionally-vulnerable OAuth/OIDC fixture for Phase-2 scanner stubs 2.14-2.17.",
  "main": "server.js",
  "private": true,
  "scripts": { "start": "node server.js" },
  "dependencies": { "express": "4.21.2" },
  "license": "MIT"
}
```

- [ ] **Step 2: Write `Dockerfile`**

```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund
COPY . .
ENV NODE_ENV=production
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost:3000/healthz || exit 1
CMD ["node", "server.js"]
```

- [ ] **Step 3: Write `lib/session.js`** (≤80 lines)

In-memory store keyed by session token. `/reset` POST wipes all entries.

```js
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
```

- [ ] **Step 4: Write `lib/oauth-helpers.js`** (≤150 lines)

OIDC discovery metadata builder, state generator, client registry.

```js
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
```

- [ ] **Step 5: Write `server.js`** (≤80 lines)

Crash on missing/unknown SCENARIO; mount scenario router; expose
`/healthz`, `/fixture-info`, `/reset`.

```js
// server.js — oauth-lab entry point. Loads scenario from SCENARIO env var.
// SAFETY: in-memory only. Never deploy outside the fixture network.
'use strict';
const express = require('express');
const session = require('./lib/session');

const SCENARIO = process.env.SCENARIO;
const PORT = parseInt(process.env.PORT || '3000', 10);

const KNOWN_SCENARIOS = ['state-missing', 'redirect-uri', 'token-sub', 'account-link'];

if (!SCENARIO || !KNOWN_SCENARIOS.includes(SCENARIO)) {
  console.error(`FATAL: SCENARIO must be one of: ${KNOWN_SCENARIOS.join(', ')}. Got: ${SCENARIO}`);
  process.exit(1);
}

// eslint-disable-next-line import/no-dynamic-require
const scenarioRouter = require(`./scenarios/${SCENARIO}`);

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: false }));

app.get('/healthz', (_req, res) => res.json({ ok: true }));
app.get('/fixture-info', (_req, res) => res.json({ scenario: SCENARIO }));
app.post('/reset', (_req, res) => {
  session.reset();
  res.json({ ok: true, message: 'in-memory state cleared' });
});

app.use('/', scenarioRouter);

app.listen(PORT, () => {
  console.log(`oauth-lab [${SCENARIO}] listening on ${PORT}`);
});
```

- [ ] **Step 6: Verify the entry point crashes on bad SCENARIO**

```bash
cd fixtures/oauth-lab && npm install
SCENARIO=unknown node server.js 2>&1 | grep FATAL
# Expected: FATAL: SCENARIO must be one of: ...
```

- [ ] **Step 7: Commit**

```bash
git add fixtures/oauth-lab/
git commit -m "feat(fixture): oauth-lab shared infra — server + session + oauth-helpers"
```
