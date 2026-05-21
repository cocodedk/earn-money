// reset-canary — purpose-built vulnerable target for Phase-2
// password-reset scanner stubs.
//
// SAFETY: in-memory state only, no persistence, no DB. Restart-each-
// scan is the explicit design. Never deploy outside the operator-owned
// fixture network.
//
// Intentional vulnerabilities:
//   * Reset tokens are epoch-ms integers (sequential, low-entropy) —
//     detectable by stub 2.5 (predictable-reset-tokens).
//   * Tokens never expire — detectable by stub 2.7 (weak-expiry).
//   * Tokens are reusable after consumption (never invalidated) —
//     detectable by stub 2.6 (reset-token-reuse).
//   * Reset link's host is built from request `X-Forwarded-Host` /
//     `Host` header without validation — detectable by stub 2.8
//     (reset-poisoning).
//   * /change-email accepts the new email with just a session token
//     (no current-password reauth) — detectable by stub 2.9
//     (account-takeover-via-email-change).
//   * /sensitive-action accepts the ordinary session token even
//     when the account has MFA enabled (no X-MFA-Step-Up check) —
//     detectable by stub 2.10 (mfa-bypass).

const crypto = require("crypto");
const express = require("express");
const nodemailer = require("nodemailer");

const PORT = parseInt(process.env.PORT || "3000", 10);
const SMTP_HOST = process.env.SMTP_HOST || "mailpit";
const SMTP_PORT = parseInt(process.env.SMTP_PORT || "1025", 10);
const PUBLIC_BASE_URL = process.env.PUBLIC_BASE_URL || `http://localhost:${PORT}`;

const mailer = nodemailer.createTransport({
  host: SMTP_HOST,
  port: SMTP_PORT,
  secure: false,
  tls: { rejectUnauthorized: false },
});

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Token -> email (intentionally predictable, intentionally never
// expires). Stored only in memory.
const tokens = new Map();

app.get("/", (_req, res) => {
  res.type("html").send(
    "<!doctype html><meta charset=utf-8><title>reset-canary</title>" +
    "<h1>reset-canary</h1>" +
    '<form action="/forgot-password" method="POST">' +
    '<input name="email" type="email" placeholder="email">' +
    '<button type="submit">Send reset link</button></form>'
  );
});

app.post("/forgot-password", async (req, res) => {
  const email = (req.body && req.body.email) || "";
  if (!email) return res.status(400).json({ error: "email required" });

  // Predictable: epoch-ms as a decimal string. Sequential across
  // back-to-back resets — exactly the signal stub 2.5 looks for.
  const token = String(Date.now());
  tokens.set(token, email);

  // Intentional vuln for stub 2.8: trust caller-supplied host
  // headers when building the reset URL. X-Forwarded-Host wins
  // over Host (mirrors the common Express-behind-proxy pattern
  // where the proxy header is treated as authoritative).
  const fwdHost = req.headers["x-forwarded-host"];
  const reqHost = req.headers["host"];
  const linkBase = fwdHost
    ? `http://${fwdHost}`
    : reqHost
      ? `http://${reqHost}`
      : PUBLIC_BASE_URL;
  const link = `${linkBase}/reset-password?token=${token}`;
  try {
    await mailer.sendMail({
      from: "noreply@reset-canary.local",
      to: email,
      subject: "Reset your password",
      text: `Click here to reset: ${link}`,
      html: `<a href="${link}">Click here to reset your password.</a>`,
    });
  } catch (err) {
    console.error("[reset-canary] mailer error", err.message);
    // Mailer failure still returns 200 — the email-existence response
    // is the contract; the inbox is just where the token lands.
  }
  return res.status(200).json({ status: "If the email exists, a reset link has been sent." });
});

app.post("/reset-password", (req, res) => {
  const token = (req.body && req.body.token) || "";
  const password = (req.body && req.body.password) || "";
  if (!token || !password) {
    return res.status(400).json({ error: "token and password required" });
  }
  const email = tokens.get(token);
  if (!email) return res.status(400).json({ error: "invalid token" });
  // Intentional: token NOT deleted after use — single-issued is the
  // only invariant. Stubs 2.6 (token-reuse) + 2.7 (weak-expiry) reach
  // here later.
  return res.status(200).json({ status: "password updated", email });
});

// ---------------------------------------------------------------------
// Stub 2.9 surface: authenticated /change-email without re-auth.
//
// In-memory user + session state. Each user is {email, password}.
// Sessions map an opaque bearer token → email (the authenticated user).
const users = new Map();      // email -> password
const sessions = new Map();   // token -> email

function _newToken() {
  return crypto.randomBytes(16).toString("hex");
}

app.post("/register", (req, res) => {
  const email = (req.body && req.body.email) || "";
  const password = (req.body && req.body.password) || "";
  if (!email || !password) {
    return res.status(400).json({ error: "email and password required" });
  }
  if (users.has(email)) return res.status(400).json({ error: "email taken" });
  users.set(email, password);
  return res.status(201).json({ status: "registered", email });
});

app.post("/login", (req, res) => {
  const email = (req.body && req.body.email) || "";
  const password = (req.body && req.body.password) || "";
  if (!users.has(email) || users.get(email) !== password) {
    return res.status(401).json({ error: "invalid credentials" });
  }
  const token = _newToken();
  sessions.set(token, email);
  return res.status(200).json({ token, email });
});

function _authedEmail(req) {
  const h = req.headers["authorization"] || "";
  const m = /^Bearer\s+(.+)$/.exec(h);
  return m ? sessions.get(m[1]) || null : null;
}

app.post("/change-email", (req, res) => {
  // Intentional vuln for stub 2.9: no current_password requirement.
  // A valid session token is enough to swap the email on the account.
  const me = _authedEmail(req);
  if (!me) return res.status(401).json({ error: "auth required" });
  const newEmail = (req.body && req.body.new_email) || "";
  if (!newEmail) return res.status(400).json({ error: "new_email required" });
  const password = users.get(me);
  users.delete(me);
  users.set(newEmail, password);
  for (const [t, e] of sessions.entries()) {
    if (e === me) sessions.set(t, newEmail);
  }
  return res.status(200).json({ status: "email changed", email: newEmail });
});

// ---------------------------------------------------------------------
// Stub 2.10 surface: MFA bypass on a sensitive endpoint.
//
// `mfaEnabled` is tracked per email. /mfa/enroll flips it true (no
// real TOTP — the canary is for back-end probe testing, not for
// validating crypto). /sensitive-action is the INTENTIONALLY-
// vulnerable endpoint: it accepts the ordinary session token even
// when the account has MFA enabled, with no `X-MFA-Step-Up` check.
const mfaState = new Map();  // email -> bool

app.post("/mfa/enroll", (req, res) => {
  const me = _authedEmail(req);
  if (!me) return res.status(401).json({ error: "auth required" });
  mfaState.set(me, true);
  return res.status(200).json({ status: "mfa_enrolled", email: me });
});

app.get("/me", (req, res) => {
  const me = _authedEmail(req);
  if (!me) return res.status(401).json({ error: "auth required" });
  return res.status(200).json({
    email: me, mfaEnabled: mfaState.get(me) === true,
  });
});

app.post("/sensitive-action", (req, res) => {
  // Intentional vuln for stub 2.10: when mfaEnabled=true on the
  // account, this endpoint is SUPPOSED to require an MFA step-up
  // (header `X-MFA-Step-Up: <code>`). It doesn't check.
  const me = _authedEmail(req);
  if (!me) return res.status(401).json({ error: "auth required" });
  return res.status(200).json({
    status: "sensitive_action_performed",
    email: me, mfaEnabled: mfaState.get(me) === true,
  });
});

app.get("/healthz", (_req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`[reset-canary] listening on :${PORT}; SMTP ${SMTP_HOST}:${SMTP_PORT}`);
});
