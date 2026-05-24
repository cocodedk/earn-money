"use strict";
const { Router } = require("express");

const router = Router();

// Static responses — just the Set-Cookie header matters for stub 3.8.

router.get("/session-cookie-long", (_req, res) => {
  res.setHeader("Set-Cookie", "sid=val; Max-Age=2592000; Path=/; Secure; HttpOnly");
  res.json({ msg: "long session cookie (30 days)" });
});

router.get("/session-cookie-short", (_req, res) => {
  res.setHeader("Set-Cookie", "sid=val; Max-Age=1800; Path=/; Secure; HttpOnly");
  res.json({ msg: "short session cookie (30 min)" });
});

router.get("/session-cookie-browser", (_req, res) => {
  res.setHeader("Set-Cookie", "sid=val; Path=/; Secure; HttpOnly");
  res.json({ msg: "browser-session cookie (no Max-Age)" });
});

router.get("/persistent-very-long", (_req, res) => {
  res.setHeader("Set-Cookie", "sid=val; Max-Age=31536000; Path=/; Secure; HttpOnly");
  res.json({ msg: "very long persistent session (1 year)" });
});

module.exports = router;
