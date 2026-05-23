"use strict";
const { Router } = require("express");
const { newToken, setCookie, getSid } = require("./helpers");

const router = Router();
const sessions = new Map();

// Helper: seed an authenticated session for testing.
router.post("/seed", (req, res) => {
  const token = newToken();
  sessions.set(token, { authenticated: true });
  setCookie(res, "sid", token);
  res.json({ msg: "session seeded" });
});

// Check: returns 200 if session exists and authenticated, else 401.
router.get("/check", (req, res) => {
  const sid = getSid(req);
  const sess = sid ? sessions.get(sid) : null;
  if (sess && sess.authenticated) return res.json({ msg: "session valid" });
  res.status(401).json({ msg: "no valid session" });
});

// Vulnerable: logout keeps session alive.
router.post("/logout-keeps-session", (req, res) => {
  const sid = getSid(req);
  if (sid && sessions.has(sid)) {
    sessions.get(sid).authenticated = false;  // marked false but NOT deleted
  }
  res.json({ msg: "logged out (session still in store)" });
});

// Safe: logout deletes session.
router.post("/logout-invalidates", (req, res) => {
  const sid = getSid(req);
  if (sid) sessions.delete(sid);
  res.json({ msg: "logged out (session deleted)" });
});

module.exports = router;
