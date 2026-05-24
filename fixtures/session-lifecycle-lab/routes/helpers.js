"use strict";
const { randomUUID } = require("crypto");

function newToken() { return randomUUID(); }

function setCookie(res, name, value) {
  res.setHeader("Set-Cookie", `${name}=${value}; Path=/; HttpOnly`);
}

function getSid(req) {
  return (req.headers.cookie || "").match(/sid=([^;]+)/)?.[1];
}

module.exports = { newToken, setCookie, getSid };
