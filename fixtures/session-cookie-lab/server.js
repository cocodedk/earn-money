// server.js — session-cookie-lab. SAFETY: never deploy outside fixture network.
'use strict';
const express = require('express');
const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);

// -- HttpOnly routes --
app.get('/httponly/missing-session', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s1; Path=/; Secure; SameSite=Lax');
  res.json({ route: 'httponly/missing-session' });
});
app.get('/httponly/present-session', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s2; Path=/; HttpOnly; Secure; SameSite=Lax');
  res.json({ route: 'httponly/present-session' });
});
app.get('/httponly/missing-framework', (_, res) => {
  res.setHeader('Set-Cookie', 'PHPSESSID=s3; Path=/');
  res.json({ route: 'httponly/missing-framework' });
});
app.get('/httponly/preference-cookie', (_, res) => {
  res.setHeader('Set-Cookie', 'theme=dark; Path=/');
  res.json({ route: 'httponly/preference-cookie' });
});
app.get('/httponly/csrf-readable', (_, res) => {
  res.setHeader('Set-Cookie', 'csrf_token=t1; Path=/; SameSite=Lax');
  res.setHeader('X-Cookie-Role', 'csrf');
  res.json({ route: 'httponly/csrf-readable' });
});
app.get('/httponly/mixed-cookies', (_, res) => {
  res.setHeader('Set-Cookie', [
    'sid=s4; Path=/; Secure',
    'track=t2; Path=/',
    'session=s5; Path=/; HttpOnly; Secure',
  ]);
  res.json({ route: 'httponly/mixed-cookies' });
});
app.get('/httponly/redirect-chain', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s6; Path=/; Secure');
  res.redirect(302, '/httponly/redirect-chain/final');
});
app.get('/httponly/redirect-chain/final', (_, res) => {
  res.json({ route: 'httponly/redirect-chain/final' });
});

// -- Secure routes --
app.get('/secure/missing-session', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s7; Path=/; HttpOnly; SameSite=Lax');
  res.json({ route: 'secure/missing-session' });
});
app.get('/secure/present-session', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s8; Path=/; Secure; HttpOnly; SameSite=Lax');
  res.json({ route: 'secure/present-session' });
});
app.get('/secure/missing-framework', (_, res) => {
  res.setHeader('Set-Cookie', 'PHPSESSID=s9; Path=/; HttpOnly');
  res.json({ route: 'secure/missing-framework' });
});
app.get('/secure/samesite-none', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s10; Path=/; HttpOnly; SameSite=None');
  res.json({ route: 'secure/samesite-none' });
});
app.get('/secure/preference-cookie', (_, res) => {
  res.setHeader('Set-Cookie', 'theme=dark; Path=/');
  res.json({ route: 'secure/preference-cookie' });
});
app.get('/secure/http-only-target', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s11; Path=/; HttpOnly');
  res.json({ route: 'secure/http-only-target' });
});
app.get('/secure/redirect-chain', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s12; Path=/; HttpOnly; SameSite=Lax');
  res.redirect(302, '/secure/redirect-chain/final');
});
app.get('/secure/redirect-chain/final', (_, res) => {
  res.json({ route: 'secure/redirect-chain/final' });
});

// -- SameSite routes --
app.get('/samesite/missing-session', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s13; Path=/; Secure; HttpOnly');
  res.json({ route: 'samesite/missing-session' });
});
app.get('/samesite/none-session', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s14; Path=/; Secure; HttpOnly; SameSite=None');
  res.json({ route: 'samesite/none-session' });
});
app.get('/samesite/none-without-secure', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s15; Path=/; HttpOnly; SameSite=None');
  res.json({ route: 'samesite/none-without-secure' });
});
app.get('/samesite/invalid', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s16; Path=/; Secure; HttpOnly; SameSite=Loose');
  res.json({ route: 'samesite/invalid' });
});
app.get('/samesite/lax-session', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s17; Path=/; Secure; HttpOnly; SameSite=Lax');
  res.json({ route: 'samesite/lax-session' });
});
app.get('/samesite/strict-session', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s18; Path=/; Secure; HttpOnly; SameSite=Strict');
  res.json({ route: 'samesite/strict-session' });
});
app.get('/samesite/allowlisted-sso', (_, res) => {
  res.setHeader('Set-Cookie', 'sso_state=val; Path=/; Secure; HttpOnly; SameSite=None');
  res.setHeader('X-Cookie-Role', 'sso');
  res.json({ route: 'samesite/allowlisted-sso' });
});
app.get('/samesite/preference-cookie', (_, res) => {
  res.setHeader('Set-Cookie', 'theme=dark; Path=/');
  res.json({ route: 'samesite/preference-cookie' });
});

// -- Domain routes --
app.get('/domain/parent-scope', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s19; Domain=example.test; Path=/; Secure; HttpOnly');
  res.json({ route: 'domain/parent-scope' });
});
app.get('/domain/deep-parent-scope', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s20; Domain=.example.test; Path=/; Secure; HttpOnly');
  res.json({ route: 'domain/deep-parent-scope' });
});
app.get('/domain/host-only', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s21; Path=/; Secure; HttpOnly');
  res.json({ route: 'domain/host-only' });
});
app.get('/domain/exact-host-domain', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s22; Domain=app.example.test; Path=/; Secure; HttpOnly');
  res.json({ route: 'domain/exact-host-domain' });
});
app.get('/domain/apex-domain', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s23; Domain=example.test; Path=/; Secure; HttpOnly');
  res.json({ route: 'domain/apex-domain' });
});
app.get('/domain/public-suffix-invalid', (_, res) => {
  res.setHeader('Set-Cookie', 'sid=s24; Domain=test; Path=/; Secure; HttpOnly');
  res.json({ route: 'domain/public-suffix-invalid' });
});
app.get('/domain/allowlisted-sso', (_, res) => {
  res.setHeader('Set-Cookie', 'sso_state=val; Domain=example.test; Path=/; Secure; HttpOnly');
  res.setHeader('X-Cookie-Role', 'sso');
  res.json({ route: 'domain/allowlisted-sso' });
});
app.get('/domain/preference-cookie', (_, res) => {
  res.setHeader('Set-Cookie', 'theme=dark; Domain=example.test; Path=/');
  res.json({ route: 'domain/preference-cookie' });
});

app.listen(PORT, () => console.log(`session-cookie-lab listening on ${PORT}`));
