// server.js — invite-tenant-lab entry point. Loads scenario from SCENARIO env var.
// SAFETY: in-memory only. Never deploy outside the fixture network.
'use strict';
const express = require('express');
const session = require('./lib/session');

const SCENARIO = process.env.SCENARIO;
const PORT = parseInt(process.env.PORT || '3000', 10);

const KNOWN_SCENARIOS = ['invitation-abuse', 'tenant-org-join'];

if (!SCENARIO || !KNOWN_SCENARIOS.includes(SCENARIO)) {
  console.error(`FATAL: SCENARIO must be one of: ${KNOWN_SCENARIOS.join(', ')}. Got: ${SCENARIO}`);
  process.exit(1);
}

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: false }));

const scenarioMod = require(`./scenarios/${SCENARIO}`);
const scenarioRouter = scenarioMod.router || scenarioMod;
const scenarioReset = typeof scenarioMod.reset === 'function' ? scenarioMod.reset : () => {};

app.get('/healthz', (_req, res) => res.json({ ok: true }));
app.get('/fixture-info', (_req, res) => res.json({ scenario: SCENARIO }));
app.post('/reset', (_req, res) => {
  session.reset();
  scenarioReset();
  res.json({ ok: true, message: 'in-memory state cleared' });
});

app.use('/', scenarioRouter);

app.listen(PORT, () => {
  console.log(`invite-tenant-lab [${SCENARIO}] listening on ${PORT}`);
});
