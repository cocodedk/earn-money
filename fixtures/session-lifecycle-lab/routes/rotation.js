"use strict";
const { Router } = require("express");
const { randomUUID } = require("crypto");

const router = Router();
const sessions = new Map();

function newToken() { return randomUUID(); }

function setCookie(res, name, value) {
  res.setHeader("Set-Cookie", `${name}=${value}; Path=/; HttpOnly`);
}

// No rotation: POST login returns same session ID as pre-login.
router.get("/login-no-rotation", (req, res) => {
  const token = newToken();
  sessions.set(token, { authenticated: false });
  setCookie(res, "sid", token);
  res.json({ msg: "pre-login session set" });
});

router.post("/login-no-rotation", (req, res) => {
  const sid = (req.headers.cookie || "").match(/sid=([^;]+)/)?.[1];
  if (sid && sessions.has(sid)) {
    sessions.get(sid).authenticated = true;
    setCookie(res, "sid", sid);          // same token — no rotation
    return res.json({ msg: "login ok, session NOT rotated" });
  }
  const token = newToken();
  sessions.set(token, { authenticated: true });
  setCookie(res, "sid", token);
  res.json({ msg: "login ok (new session)" });
});

// Rotates: POST login issues a new session ID.
router.get("/login-rotates", (req, res) => {
  const token = newToken();
  sessions.set(token, { authenticated: false });
  setCookie(res, "sid", token);
  res.json({ msg: "pre-login session set" });
});

router.post("/login-rotates", (req, res) => {
  const old = (req.headers.cookie || "").match(/sid=([^;]+)/)?.[1];
  if (old) sessions.delete(old);
  const token = newToken();
  sessions.set(token, { authenticated: true });
  setCookie(res, "sid", token);
  res.json({ msg: "login ok, session rotated" });
});

module.exports = router;
