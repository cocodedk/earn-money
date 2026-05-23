"use strict";
const { Router } = require("express");
const { newToken, setCookie, getSid } = require("./helpers");

const router = Router();

// In-memory session store shared within this route module.
const sessions = new Map();

// Vulnerable: GET sets anon sid; POST login keeps same sid.
router.get("/login-vulnerable", (req, res) => {
  const token = newToken();
  sessions.set(token, { authenticated: false });
  setCookie(res, "sid", token);
  res.json({ msg: "anon session set" });
});

router.post("/login-vulnerable", (req, res) => {
  const sid = getSid(req);
  if (sid && sessions.has(sid)) {
    sessions.get(sid).authenticated = true;
    setCookie(res, "sid", sid);          // same token — fixation
    return res.json({ msg: "login ok, session NOT rotated" });
  }
  const token = newToken();
  sessions.set(token, { authenticated: true });
  setCookie(res, "sid", token);
  res.json({ msg: "login ok (new session)" });
});

// Safe: POST login rotates sid.
router.get("/login-rotates", (req, res) => {
  const token = newToken();
  sessions.set(token, { authenticated: false });
  setCookie(res, "sid", token);
  res.json({ msg: "anon session set" });
});

router.post("/login-rotates", (req, res) => {
  const old = getSid(req);
  if (old) sessions.delete(old);
  const token = newToken();
  sessions.set(token, { authenticated: true });
  setCookie(res, "sid", token);
  res.json({ msg: "login ok, session rotated" });
});

// Safe: no pre-cookie at all.
router.post("/login-no-pre-cookie", (req, res) => {
  const token = newToken();
  sessions.set(token, { authenticated: true });
  setCookie(res, "sid", token);
  res.json({ msg: "login ok (fresh session)" });
});

// Vulnerable: externally seeded sid preserved.
router.post("/cookie-seed-vulnerable", (req, res) => {
  const sid = getSid(req);
  if (sid) {
    sessions.set(sid, { authenticated: true });
    setCookie(res, "sid", sid);          // preserves attacker-seeded value
    return res.json({ msg: "session accepted as-is" });
  }
  const token = newToken();
  sessions.set(token, { authenticated: true });
  setCookie(res, "sid", token);
  res.json({ msg: "new session" });
});

// Safe: replaces externally seeded sid.
router.post("/cookie-seed-safe", (req, res) => {
  const token = newToken();
  sessions.set(token, { authenticated: true });
  setCookie(res, "sid", token);
  res.json({ msg: "seed replaced with new session" });
});

module.exports = router;
