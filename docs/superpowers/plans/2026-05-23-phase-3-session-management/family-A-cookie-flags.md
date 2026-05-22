# Family A — Cookie Flags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `session-cookie-lab` fixture + shared cookie parser + stubs 3.1–3.4.

**Architecture:** Node.js fixture (`fixtures/session-cookie-lab/`) serves deterministic
`Set-Cookie` routes. Python shared parser (`_shared/session/cookie_parser.py`) extracts
cookie attributes. Four stubs (`missing_httponly`, `missing_secure`, `weak_samesite`,
`broad_domain_scope`) classify and emit `Finding` + `Evidence`.

**Tech Stack:** Node 22/Express 4, Python 3.12/Django, pytest/httpx, docker-compose.

**Branch:** `feat/em-backend-phase-3-cookie-flags` (stacked on `main` tip).

---

## Task index

| # | Task | Produces |
|---|------|---------|
| 01 | Fixture: `session-cookie-lab` | `fixtures/session-cookie-lab/` |
| 02 | Shared cookie parser | `_shared/session/cookie_parser.py` + tests |
| 03 | Stub 3.1 — missing_httponly | `stubs/missing_httponly/` |
| 04 | Stub 3.2 — missing_secure | `stubs/missing_secure/` |
| 05 | Stub 3.3 — weak_samesite | `stubs/weak_samesite/` |
| 06 | Stub 3.4 — broad_domain_scope | `stubs/broad_domain_scope/` |
| 07 | docker-compose wiring | `docker-compose.yml` service block |

---

## Task 01: Fixture `session-cookie-lab`

**Files:**
- Create: `fixtures/session-cookie-lab/package.json`
- Create: `fixtures/session-cookie-lab/server.js`
- Create: `fixtures/session-cookie-lab/Dockerfile`

### Cookie attribute routes served

All four specs share the `session-cookie-attributes` fixture slug.

**HttpOnly routes** (`/httponly/*`):

| Route | `Set-Cookie` header |
|-------|---------------------|
| `/httponly/missing-session` | `sid=s1; Path=/; Secure; SameSite=Lax` |
| `/httponly/present-session` | `sid=s2; Path=/; HttpOnly; Secure; SameSite=Lax` |
| `/httponly/missing-framework` | `PHPSESSID=s3; Path=/` |
| `/httponly/preference-cookie` | `theme=dark; Path=/` |
| `/httponly/csrf-readable` | `csrf_token=t1; Path=/; SameSite=Lax` (add header `X-Cookie-Role: csrf`) |
| `/httponly/mixed-cookies` | `sid=s4; Path=/; Secure` + `track=t2; Path=/` + `session=s5; Path=/; HttpOnly; Secure` |
| `/httponly/redirect-chain` | 302 → `/httponly/redirect-chain/final` with `sid=s6; Path=/; Secure` on redirect |

**Secure routes** (`/secure/*`):

| Route | `Set-Cookie` header |
|-------|---------------------|
| `/secure/missing-session` | `sid=s7; Path=/; HttpOnly; SameSite=Lax` |
| `/secure/present-session` | `sid=s8; Path=/; Secure; HttpOnly; SameSite=Lax` |
| `/secure/missing-framework` | `PHPSESSID=s9; Path=/; HttpOnly` |
| `/secure/samesite-none` | `sid=s10; Path=/; HttpOnly; SameSite=None` |
| `/secure/preference-cookie` | `theme=dark; Path=/` |
| `/secure/http-only-target` | `sid=s11; Path=/; HttpOnly` (respond HTTP 200 regardless of scheme) |
| `/secure/redirect-chain` | 302 with `sid=s12; Path=/; HttpOnly; SameSite=Lax` on redirect |

**SameSite routes** (`/samesite/*`):

| Route | `Set-Cookie` header |
|-------|---------------------|
| `/samesite/missing-session` | `sid=s13; Path=/; Secure; HttpOnly` |
| `/samesite/none-session` | `sid=s14; Path=/; Secure; HttpOnly; SameSite=None` |
| `/samesite/none-without-secure` | `sid=s15; Path=/; HttpOnly; SameSite=None` |
| `/samesite/invalid` | `sid=s16; Path=/; Secure; HttpOnly; SameSite=Loose` |
| `/samesite/lax-session` | `sid=s17; Path=/; Secure; HttpOnly; SameSite=Lax` |
| `/samesite/strict-session` | `sid=s18; Path=/; Secure; HttpOnly; SameSite=Strict` |
| `/samesite/allowlisted-sso` | `sso_state=val; Path=/; Secure; HttpOnly; SameSite=None` (header `X-Cookie-Role: sso`) |
| `/samesite/preference-cookie` | `theme=dark; Path=/` |

**Domain routes** (`/domain/*`):

| Route | Host context | `Set-Cookie` header |
|-------|--------------|---------------------|
| `/domain/parent-scope` | `app.example.test` | `sid=s19; Domain=example.test; Path=/; Secure; HttpOnly` |
| `/domain/deep-parent-scope` | `admin.eu.example.test` | `sid=s20; Domain=.example.test; Path=/; Secure; HttpOnly` |
| `/domain/host-only` | `app.example.test` | `sid=s21; Path=/; Secure; HttpOnly` |
| `/domain/exact-host-domain` | `app.example.test` | `sid=s22; Domain=app.example.test; Path=/; Secure; HttpOnly` |
| `/domain/apex-domain` | `example.test` | `sid=s23; Domain=example.test; Path=/; Secure; HttpOnly` |
| `/domain/public-suffix-invalid` | `app.example.test` | `sid=s24; Domain=test; Path=/; Secure; HttpOnly` |
| `/domain/allowlisted-sso` | `app.example.test` | `sso_state=val; Domain=example.test; Path=/; Secure; HttpOnly` (header `X-Cookie-Role: sso`) |
| `/domain/preference-cookie` | `app.example.test` | `theme=dark; Domain=example.test; Path=/` |

- [ ] **Step 1.1: Write `package.json`**

```json
{
  "name": "session-cookie-lab",
  "version": "0.1.0",
  "description": "Deterministic cookie-attribute fixture for Phase-3 stubs 3.1-3.4.",
  "main": "server.js",
  "private": true,
  "scripts": { "start": "node server.js" },
  "dependencies": { "express": "4.21.2" },
  "license": "MIT"
}
```

- [ ] **Step 1.2: Write `server.js`**

```js
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
```

- [ ] **Step 1.3: Write `Dockerfile`**

```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY server.js ./
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 1.4: Run `npm install` in `fixtures/session-cookie-lab/`**

```bash
cd fixtures/session-cookie-lab && npm install && cd ../..
```

- [ ] **Step 1.5: Smoke-test fixture locally**

```bash
cd fixtures/session-cookie-lab && node server.js &
sleep 1
curl -si http://localhost:3000/httponly/missing-session | grep Set-Cookie
# Expected: sid=s1; Path=/; Secure; SameSite=Lax  (no HttpOnly)
curl -si http://localhost:3000/httponly/present-session | grep Set-Cookie
# Expected: sid=s2; Path=/; HttpOnly; Secure; SameSite=Lax
kill %1
```

- [ ] **Step 1.6: Commit fixture**

```bash
git add fixtures/session-cookie-lab/
git commit -m "feat(fixtures): session-cookie-lab — cookie-attribute routes for stubs 3.1-3.4"
```

---

## Task 02: Shared cookie parser

**Files:**
- Create: `backend/apps/stubs/_shared/session/__init__.py`
- Create: `backend/apps/stubs/_shared/session/cookie_parser.py`
- Create: `backend/apps/stubs/_shared/session/tests/__init__.py`
- Create: `backend/apps/stubs/_shared/session/tests/test_cookie_parser.py`

- [ ] **Step 2.1: Write failing tests first**

`backend/apps/stubs/_shared/session/tests/test_cookie_parser.py`:

```python
"""Tests for the shared cookie parser."""
from __future__ import annotations
import pytest
from apps.stubs._shared.session.cookie_parser import (
    ParsedCookie, parse_set_cookie, is_sensitive_cookie,
    Sensitivity, CookieCategory,
)


def test_parses_name_and_value():
    c = parse_set_cookie("sid=abc123")
    assert c.name == "sid" and c.value_redacted is not None


def test_httponly_present_case_insensitive():
    for attr in ("HttpOnly", "httponly", "HTTPONLY"):
        c = parse_set_cookie(f"sid=x; Path=/; {attr}")
        assert c.httponly is True, f"failed for: {attr}"


def test_httponly_absent():
    c = parse_set_cookie("sid=x; Path=/; Secure; SameSite=Lax")
    assert c.httponly is False


def test_secure_present():
    c = parse_set_cookie("sid=x; Secure; HttpOnly")
    assert c.secure is True


def test_secure_absent():
    c = parse_set_cookie("sid=x; HttpOnly")
    assert c.secure is False


def test_samesite_values():
    for val in ("Strict", "Lax", "None"):
        c = parse_set_cookie(f"sid=x; SameSite={val}")
        assert c.samesite == val


def test_samesite_missing_is_none():
    c = parse_set_cookie("sid=x")
    assert c.samesite is None


def test_samesite_invalid_value():
    c = parse_set_cookie("sid=x; SameSite=Loose")
    assert c.samesite == "Loose"


def test_domain_extracted():
    c = parse_set_cookie("sid=x; Domain=example.test; Path=/")
    assert c.domain == "example.test"


def test_domain_leading_dot_stripped():
    c = parse_set_cookie("sid=x; Domain=.example.test")
    assert c.domain == "example.test"


def test_path_extracted():
    c = parse_set_cookie("sid=x; Path=/app")
    assert c.path == "/app"


def test_max_age_extracted():
    c = parse_set_cookie("sid=x; Max-Age=3600")
    assert c.max_age == 3600


def test_expires_extracted():
    c = parse_set_cookie("sid=x; Expires=Thu, 01 Jan 2099 00:00:00 GMT")
    assert c.expires is not None


def test_value_is_redacted():
    c = parse_set_cookie("PHPSESSID=supersecret1234567890; Path=/")
    assert "supersecret1234567890" not in (c.value_redacted or "")


def test_framework_session_high_sensitivity():
    for name in ("PHPSESSID", "JSESSIONID", "connect.sid", "ASP.NET_SessionId"):
        s = is_sensitive_cookie(name)
        assert s == Sensitivity.HIGH, f"{name} should be HIGH"


def test_session_name_high_sensitivity():
    for name in ("session", "sid", "auth", "access_token", "refresh_token", "jwt"):
        assert is_sensitive_cookie(name) == Sensitivity.HIGH


def test_medium_sensitivity_names():
    for name in ("my_session_id", "auth_helper", "token_store", "remember_me"):
        assert is_sensitive_cookie(name) == Sensitivity.MEDIUM


def test_preference_cookie_low():
    for name in ("theme", "locale", "_ga", "ab_test", "consent"):
        assert is_sensitive_cookie(name) == Sensitivity.LOW


def test_csrf_token_low_by_default():
    assert is_sensitive_cookie("csrf_token") == Sensitivity.LOW


def test_cookie_category_framework():
    c = parse_set_cookie("PHPSESSID=x; Path=/")
    assert c.category == CookieCategory.FRAMEWORK_SESSION


def test_cookie_category_session():
    c = parse_set_cookie("session=x; Path=/")
    assert c.category == CookieCategory.SESSION
```

- [ ] **Step 2.2: Run tests — expect ImportError / FAIL**

```bash
cd backend && python -m pytest apps/stubs/_shared/session/tests/test_cookie_parser.py -v 2>&1 | head -20
```

- [ ] **Step 2.3: Implement `cookie_parser.py`**

`backend/apps/stubs/_shared/session/cookie_parser.py`:

```python
"""Shared cookie-attribute parser for Phase-3 session-management stubs."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Sensitivity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CookieCategory(str, Enum):
    SESSION = "session"
    AUTH = "auth"
    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"
    REMEMBER_ME = "remember_me"
    FRAMEWORK_SESSION = "framework_session"
    CSRF_SESSION = "csrf_session"
    UNKNOWN = "unknown"


_FRAMEWORK_NAMES: frozenset[str] = frozenset({
    "PHPSESSID", "JSESSIONID", "connect.sid", "ASP.NET_SessionId",
    "ASP_NET_SessionId", "ASPSESSIONID",
})
_HIGH_NAMES: frozenset[str] = frozenset({
    "session", "sid", "auth", "access_token", "refresh_token",
    "id_token", "jwt", "token",
})
_MEDIUM_PATTERN = re.compile(
    r"(session|sess|auth|token|login|remember|sso)", re.IGNORECASE
)
_CSRF_PATTERN = re.compile(r"csrf", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedCookie:
    name: str
    value_redacted: Optional[str]
    domain: Optional[str]
    path: Optional[str]
    expires: Optional[str]
    max_age: Optional[int]
    secure: bool
    httponly: bool
    samesite: Optional[str]
    sensitivity: Sensitivity
    category: CookieCategory
    raw_set_cookie: str


def parse_set_cookie(header: str) -> ParsedCookie:
    parts = [p.strip() for p in header.split(";")]
    name_val = parts[0]
    name, _, raw_value = name_val.partition("=")
    name = name.strip()
    value_redacted = _redact(raw_value.strip()) if raw_value else None

    attrs: dict[str, Optional[str]] = {}
    for part in parts[1:]:
        key, _, val = part.partition("=")
        attrs[key.strip().lower()] = val.strip() if val else None

    domain_raw = attrs.get("domain")
    domain = domain_raw.lstrip(".") if domain_raw else None
    samesite_raw = attrs.get("samesite")

    max_age_raw = attrs.get("max-age")
    max_age: Optional[int] = None
    if max_age_raw is not None:
        try:
            max_age = int(max_age_raw)
        except ValueError:
            pass

    sensitivity = is_sensitive_cookie(name)
    category = _classify_category(name)

    return ParsedCookie(
        name=name,
        value_redacted=value_redacted,
        domain=domain,
        path=attrs.get("path"),
        expires=attrs.get("expires"),
        max_age=max_age,
        secure="secure" in attrs,
        httponly="httponly" in attrs,
        samesite=samesite_raw,
        sensitivity=sensitivity,
        category=category,
        raw_set_cookie=_redact_header(header),
    )


def is_sensitive_cookie(name: str) -> Sensitivity:
    if name in _FRAMEWORK_NAMES:
        return Sensitivity.HIGH
    if name.lower() in {n.lower() for n in _HIGH_NAMES}:
        return Sensitivity.HIGH
    if _CSRF_PATTERN.search(name):
        return Sensitivity.LOW
    if _MEDIUM_PATTERN.search(name):
        return Sensitivity.MEDIUM
    return Sensitivity.LOW


def _classify_category(name: str) -> CookieCategory:
    if name in _FRAMEWORK_NAMES:
        return CookieCategory.FRAMEWORK_SESSION
    nl = name.lower()
    if nl in ("session", "sid"):
        return CookieCategory.SESSION
    if nl in ("auth",):
        return CookieCategory.AUTH
    if "access_token" in nl:
        return CookieCategory.ACCESS_TOKEN
    if "refresh_token" in nl:
        return CookieCategory.REFRESH_TOKEN
    if "remember" in nl:
        return CookieCategory.REMEMBER_ME
    if _CSRF_PATTERN.search(name):
        return CookieCategory.CSRF_SESSION
    if _MEDIUM_PATTERN.search(name):
        return CookieCategory.SESSION
    return CookieCategory.UNKNOWN


def _redact(value: str) -> str:
    h = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f"<redacted:{h}>"


def _redact_header(header: str) -> str:
    parts = header.split(";")
    name_val = parts[0]
    name, _, _ = name_val.partition("=")
    return name.strip() + "=<redacted>;" + ";".join(parts[1:])
```

- [ ] **Step 2.4: Run tests — expect PASS**

```bash
cd backend && python -m pytest apps/stubs/_shared/session/tests/test_cookie_parser.py -v
```
Expected: all green.

- [ ] **Step 2.5: Commit**

```bash
git add backend/apps/stubs/_shared/session/
git commit -m "feat(session): shared cookie parser — Phase-3 attribute extraction"
```

---

## Task 03: Stub 3.1 — missing_httponly

**Files:**
- Create: `backend/apps/stubs/missing_httponly/__init__.py`
- Create: `backend/apps/stubs/missing_httponly/classify.py`
- Create: `backend/apps/stubs/missing_httponly/runner.py`
- Create: `backend/apps/stubs/missing_httponly/tests/__init__.py`
- Create: `backend/apps/stubs/missing_httponly/tests/test_classify.py`
- Create: `backend/apps/stubs/missing_httponly/tests/test_runner.py`

- [ ] **Step 3.1: Write failing classify tests**

`backend/apps/stubs/missing_httponly/tests/test_classify.py`:

```python
"""Tests for stub 3.1 missing-httponly classification."""
from __future__ import annotations
import pytest
from apps.stubs.missing_httponly.classify import (
    classify_cookie, HttpOnlyResult, HttpOnlyStatus,
)
from apps.stubs._shared.session.cookie_parser import parse_set_cookie


def _c(header: str):
    return parse_set_cookie(header)


def test_high_sensitivity_missing_httponly_confirmed():
    r = classify_cookie(_c("sid=x; Path=/; Secure; SameSite=Lax"), authenticated=True)
    assert r.status == HttpOnlyStatus.CONFIRMED
    assert r.confidence == "high"


def test_framework_cookie_missing_httponly_confirmed():
    r = classify_cookie(_c("PHPSESSID=x; Path=/"), authenticated=False)
    assert r.status == HttpOnlyStatus.CONFIRMED
    assert r.confidence == "high"


def test_auth_looking_no_auth_context_candidate():
    r = classify_cookie(_c("connect.sid=x; Path=/; Secure; SameSite=Lax"), authenticated=False)
    assert r.status == HttpOnlyStatus.CANDIDATE


def test_httponly_present_rejected():
    r = classify_cookie(
        _c("sid=x; Path=/; HttpOnly; Secure; SameSite=Lax"), authenticated=True
    )
    assert r.status == HttpOnlyStatus.REJECTED
    assert r.confidence == "high"


def test_preference_cookie_no_finding():
    r = classify_cookie(_c("theme=dark; Path=/"), authenticated=False)
    assert r.status == HttpOnlyStatus.NOT_APPLICABLE


def test_csrf_token_no_finding_by_default():
    r = classify_cookie(_c("csrf_token=t; Path=/; SameSite=Lax"), authenticated=False)
    assert r.status == HttpOnlyStatus.NOT_APPLICABLE


def test_medium_sensitivity_no_auth_is_candidate():
    r = classify_cookie(_c("my_session=x; Path=/; Secure"), authenticated=False)
    assert r.status == HttpOnlyStatus.CANDIDATE
    assert r.confidence == "medium"


def test_raw_value_not_in_result():
    r = classify_cookie(_c("PHPSESSID=supersecret; Path=/"), authenticated=False)
    assert "supersecret" not in str(r)
```

- [ ] **Step 3.2: Run tests — expect FAIL (module missing)**

```bash
cd backend && python -m pytest apps/stubs/missing_httponly/tests/test_classify.py -v 2>&1 | head -10
```

- [ ] **Step 3.3: Write `classify.py`**

`backend/apps/stubs/missing_httponly/classify.py`:

```python
"""Stub 3.1 — Missing HttpOnly classification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity


class HttpOnlyStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class HttpOnlyResult:
    status: HttpOnlyStatus
    confidence: Literal["low", "medium", "high"]
    cookie_name: str
    raw_set_cookie: str


def classify_cookie(cookie: ParsedCookie, *, authenticated: bool) -> HttpOnlyResult:
    if cookie.sensitivity == Sensitivity.LOW:
        return HttpOnlyResult(
            status=HttpOnlyStatus.NOT_APPLICABLE,
            confidence="high",
            cookie_name=cookie.name,
            raw_set_cookie=cookie.raw_set_cookie,
        )
    if cookie.httponly:
        return HttpOnlyResult(
            status=HttpOnlyStatus.REJECTED,
            confidence="high",
            cookie_name=cookie.name,
            raw_set_cookie=cookie.raw_set_cookie,
        )
    # Missing HttpOnly
    if authenticated or cookie.sensitivity == Sensitivity.HIGH:
        return HttpOnlyResult(
            status=HttpOnlyStatus.CONFIRMED,
            confidence="high",
            cookie_name=cookie.name,
            raw_set_cookie=cookie.raw_set_cookie,
        )
    return HttpOnlyResult(
        status=HttpOnlyStatus.CANDIDATE,
        confidence="medium",
        cookie_name=cookie.name,
        raw_set_cookie=cookie.raw_set_cookie,
    )
```

- [ ] **Step 3.4: Run classify tests — expect PASS**

```bash
cd backend && python -m pytest apps/stubs/missing_httponly/tests/test_classify.py -v
```

- [ ] **Step 3.5: Write failing runner tests**

`backend/apps/stubs/missing_httponly/tests/test_runner.py`:

```python
"""Tests for stub 3.1 runner — missing HttpOnly."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
import httpx

from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs.missing_httponly.runner import run


@pytest.fixture
def scan_run(db):
    from apps.projects.models import Project
    p = Project.objects.create(name="p")
    return ScanRun.objects.create(project=p, stub_slug="3.1")


@pytest.fixture
def target_run(scan_run, db):
    from apps.targets.models import ScanTarget
    t = ScanTarget.objects.create(
        project=scan_run.project,
        base_url="http://fixture:3000",
        host="fixture",
    )
    return ScanTargetRun.objects.create(scan_run=scan_run, target=t)


@pytest.fixture
def program():
    p = MagicMock()
    p.roe.allow_passive_cookie_checks = True
    p.slug = "test"
    return p


def _resp(headers: dict) -> httpx.Response:
    return httpx.Response(200, headers=headers)


@pytest.mark.django_db
def test_finding_for_missing_httponly(scan_run, target_run, program):
    resp = _resp({"Set-Cookie": "sid=x; Path=/; Secure; SameSite=Lax"})
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        with patch("apps.programs.rate_limit.acquire_for"):
            run(scan_run, target_run, program=program)
    from apps.findings.models import Finding
    assert Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_no_finding_when_httponly_present(scan_run, target_run, program):
    resp = _resp({"Set-Cookie": "sid=x; Path=/; HttpOnly; Secure; SameSite=Lax"})
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        with patch("apps.programs.rate_limit.acquire_for"):
            run(scan_run, target_run, program=program)
    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_no_finding_for_preference_cookie(scan_run, target_run, program):
    resp = _resp({"Set-Cookie": "theme=dark; Path=/"})
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        with patch("apps.programs.rate_limit.acquire_for"):
            run(scan_run, target_run, program=program)
    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_refusal_when_roe_disabled(scan_run, target_run):
    program = MagicMock()
    program.roe.allow_passive_cookie_checks = False
    run(scan_run, target_run, program=program)
    from apps.findings.models import Finding
    assert not Finding.objects.filter(stub_slug="3.1").exists()


@pytest.mark.django_db
def test_no_crash_on_no_cookies(scan_run, target_run, program):
    resp = _resp({})
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=resp):
        with patch("apps.programs.rate_limit.acquire_for"):
            run(scan_run, target_run, program=program)  # must not raise


@pytest.mark.django_db
def test_no_crash_on_transport_error(scan_run, target_run, program):
    with patch("apps.stubs.missing_httponly.runner.submit_probe", return_value=None):
        with patch("apps.programs.rate_limit.acquire_for"):
            run(scan_run, target_run, program=program)  # must not raise
```

- [ ] **Step 3.6: Write `runner.py`**

`backend/apps/stubs/missing_httponly/runner.py`:

```python
"""Stub 3.1 runner — missing-httponly."""
from __future__ import annotations

import httpx

from apps.findings.models import Finding, FindingStatus, Severity
from apps.programs.loader import Program
from apps.programs.rate_limit import acquire_for
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._shared.auth.events import log_finding_candidate
from apps.stubs._shared.auth.requests import submit_probe
from apps.stubs._shared.auth.safety import RefusalReason, record_refusal
from apps.stubs._shared.session.cookie_parser import parse_set_cookie, Sensitivity

from ..runners import guarded_runner
from .classify import classify_cookie, HttpOnlyStatus

_STUB_ID = "3.1"
_MAX_REQUESTS = 4


@guarded_runner(_STUB_ID)
def run(scan_run: ScanRun, target_run: ScanTargetRun, *, program: Program) -> None:
    if not program.roe.allow_passive_cookie_checks:
        record_refusal(
            scan_run=scan_run, target_run=target_run, stub_id=_STUB_ID,
            reason=RefusalReason.ROE_DISABLED,
            details={"knob": "allow_passive_cookie_checks"},
        )
        return

    target = target_run.target
    base = target.base_url.rstrip("/")
    acquire_for(program)

    urls = [base + "/", base + "/login"][:_MAX_REQUESTS]
    for url in urls:
        req = httpx.Request("GET", url)
        resp = submit_probe(req)
        if resp is None:
            continue
        _process_response(resp, scan_run=scan_run, target_run=target_run)


def _process_response(
    resp: httpx.Response,
    *,
    scan_run: ScanRun,
    target_run: ScanTargetRun,
) -> None:
    raw_cookies = resp.headers.get_list("Set-Cookie")
    for raw in raw_cookies:
        cookie = parse_set_cookie(raw)
        result = classify_cookie(cookie, authenticated=False)
        if result.status in (HttpOnlyStatus.CONFIRMED, HttpOnlyStatus.CANDIDATE):
            _emit_finding(scan_run=scan_run, target_run=target_run, cookie_name=cookie.name,
                          raw_header=cookie.raw_set_cookie, status=result.status.value,
                          confidence=result.confidence)


def _emit_finding(
    *, scan_run: ScanRun, target_run: ScanTargetRun,
    cookie_name: str, raw_header: str,
    status: str, confidence: str,
) -> None:
    finding = Finding.objects.create(
        scan_run=scan_run,
        target=target_run.target,
        stub_slug=_STUB_ID,
        title=f"Session cookie '{cookie_name}' missing HttpOnly attribute",
        category="missing_httponly",
        severity=Severity.MEDIUM,
        confidence=confidence,
        status=FindingStatus.CONFIRMED if status == "confirmed" else FindingStatus.CANDIDATE,
        data={"cookie_name": cookie_name, "raw_set_cookie": raw_header},
    )
    log_finding_candidate(finding, stub_id=_STUB_ID)
```

- [ ] **Step 3.7: Run all stub 3.1 tests**

```bash
cd backend && python -m pytest apps/stubs/missing_httponly/ -v
```
Expected: all green.

- [ ] **Step 3.8: Check coverage**

```bash
cd backend && python -m pytest apps/stubs/missing_httponly/ --cov=apps/stubs/missing_httponly --cov-report=term-missing
```
Expected: 100% or near-100% on classify.py and runner.py.

- [ ] **Step 3.9: Commit**

```bash
git add backend/apps/stubs/missing_httponly/
git commit -m "feat(stubs): 3.1 missing-httponly — HttpOnly attribute detection"
```

---

## Task 04: Stub 3.2 — missing_secure

**Files:**
- Create: `backend/apps/stubs/missing_secure/__init__.py`
- Create: `backend/apps/stubs/missing_secure/classify.py`
- Create: `backend/apps/stubs/missing_secure/runner.py`
- Create: `backend/apps/stubs/missing_secure/tests/__init__.py`
- Create: `backend/apps/stubs/missing_secure/tests/test_classify.py`
- Create: `backend/apps/stubs/missing_secure/tests/test_runner.py`

- [ ] **Step 4.1: Write failing classify tests**

`backend/apps/stubs/missing_secure/tests/test_classify.py`:

```python
"""Tests for stub 3.2 missing-secure classification."""
from __future__ import annotations
from apps.stubs.missing_secure.classify import (
    classify_cookie, SecureResult, SecureStatus,
)
from apps.stubs._shared.session.cookie_parser import parse_set_cookie


def _c(header: str):
    return parse_set_cookie(header)


def test_https_missing_secure_confirmed():
    r = classify_cookie(_c("sid=x; Path=/; HttpOnly; SameSite=Lax"), scheme="https")
    assert r.status == SecureStatus.CONFIRMED and r.confidence == "high"


def test_framework_missing_secure_confirmed():
    r = classify_cookie(_c("PHPSESSID=x; Path=/; HttpOnly"), scheme="https")
    assert r.status == SecureStatus.CONFIRMED and r.confidence == "high"


def test_samesite_none_missing_secure_confirmed():
    r = classify_cookie(_c("sid=x; Path=/; HttpOnly; SameSite=None"), scheme="https")
    assert r.status == SecureStatus.CONFIRMED and r.confidence == "high"


def test_http_scheme_candidate():
    r = classify_cookie(_c("sid=x; Path=/; HttpOnly"), scheme="http")
    assert r.status == SecureStatus.CANDIDATE and r.confidence == "medium"


def test_secure_present_rejected():
    r = classify_cookie(_c("sid=x; Path=/; Secure; HttpOnly; SameSite=Lax"), scheme="https")
    assert r.status == SecureStatus.REJECTED and r.confidence == "high"


def test_preference_cookie_not_applicable():
    r = classify_cookie(_c("theme=dark; Path=/"), scheme="https")
    assert r.status == SecureStatus.NOT_APPLICABLE
```

- [ ] **Step 4.2: Write `classify.py`**

`backend/apps/stubs/missing_secure/classify.py`:

```python
"""Stub 3.2 — Missing Secure classification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity


class SecureStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class SecureResult:
    status: SecureStatus
    confidence: Literal["low", "medium", "high"]
    cookie_name: str
    raw_set_cookie: str


def classify_cookie(cookie: ParsedCookie, *, scheme: str) -> SecureResult:
    if cookie.sensitivity == Sensitivity.LOW:
        return SecureResult(
            status=SecureStatus.NOT_APPLICABLE, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    if cookie.secure:
        return SecureResult(
            status=SecureStatus.REJECTED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    # SameSite=None without Secure is always confirmed regardless of scheme
    if cookie.samesite and cookie.samesite.lower() == "none":
        return SecureResult(
            status=SecureStatus.CONFIRMED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    if scheme == "https":
        return SecureResult(
            status=SecureStatus.CONFIRMED, confidence="high",
            cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
        )
    return SecureResult(
        status=SecureStatus.CANDIDATE, confidence="medium",
        cookie_name=cookie.name, raw_set_cookie=cookie.raw_set_cookie,
    )
```

- [ ] **Step 4.3: Write runner and tests** (mirror stub 3.1 pattern, change `_STUB_ID = "3.2"`, category `"missing_secure"`, check `cookie.secure`)

- [ ] **Step 4.4: Run all stub 3.2 tests and commit**

```bash
cd backend && python -m pytest apps/stubs/missing_secure/ -v
git add backend/apps/stubs/missing_secure/
git commit -m "feat(stubs): 3.2 missing-secure — Secure attribute detection"
```

---

## Task 05: Stub 3.3 — weak_samesite

**Files:**
- Create: `backend/apps/stubs/weak_samesite/__init__.py`
- Create: `backend/apps/stubs/weak_samesite/classify.py`
- Create: `backend/apps/stubs/weak_samesite/runner.py`
- Create: `backend/apps/stubs/weak_samesite/tests/`

`classify.py` must handle `weakness_kind` values: `missing_samesite`, `explicit_none`,
`none_without_secure`, `invalid_samesite`, `lax_where_strict_required`.

- [ ] **Step 5.1: Write failing classify tests covering all weakness kinds**

Key assertions:
- `sid` + no SameSite → `candidate` / `medium` / `missing_samesite`
- `sid` + `SameSite=None` + `Secure` → `candidate` / `high` / `explicit_none`
- `sid` + `SameSite=None` + no `Secure` → `confirmed` / `high` / `none_without_secure`
- `sid` + `SameSite=Loose` → `confirmed` / `medium` / `invalid_samesite`
- `sid` + `SameSite=Lax` → `rejected` / `high` (no weakness)
- `sso_state` with header `X-Cookie-Role: sso` → allowlist → `NOT_APPLICABLE`
- `theme=dark` → `NOT_APPLICABLE`

- [ ] **Step 5.2: Write `classify.py`**, **Step 5.3: Write runner + tests**, **Step 5.4: Run + commit**

```bash
git add backend/apps/stubs/weak_samesite/
git commit -m "feat(stubs): 3.3 weak-samesite — SameSite weakness detection"
```

---

## Task 06: Stub 3.4 — broad_domain_scope

**Files:**
- Create: `backend/apps/stubs/broad_domain_scope/__init__.py`
- Create: `backend/apps/stubs/broad_domain_scope/classify.py`
- Create: `backend/apps/stubs/broad_domain_scope/runner.py`
- Create: `backend/apps/stubs/broad_domain_scope/tests/`

`classify.py` must compute `scope_issue` from: `parent_domain`, `apex_domain`,
`exact_host_domain_attribute`, `public_suffix_invalid`.

Key logic:
- `Domain=example.test` when response host is `app.example.test` → `parent_domain` → `confirmed`/`high`
- `Domain=.example.test` → leading dot stripped → same as above
- No domain attribute (host-only) → `rejected`/`high`
- `Domain=app.example.test` matching host exactly → `exact_host_domain_attribute` → `candidate`/`low`
- `Domain=example.test` from apex host `example.test` → `apex_domain` → `candidate`/`medium`
- `Domain=test` (public suffix) → `public_suffix_invalid` → `rejected`
- preference cookies → `NOT_APPLICABLE`

- [ ] **Step 6.1: Write failing classify tests**, **Step 6.2: Write `classify.py`**,
  **Step 6.3: Write runner + tests**, **Step 6.4: Run + commit**

```bash
git add backend/apps/stubs/broad_domain_scope/
git commit -m "feat(stubs): 3.4 broad-domain-scope — cookie domain scope detection"
```

---

## Task 07: docker-compose wiring

**Files:**
- Modify: `docker-compose.yml`

Add service block:

```yaml
  session-cookie-lab:
    build: ./fixtures/session-cookie-lab
    image: earnmoney-session-cookie-lab:dev
    ports:
      - "3004:3000"
    networks:
      - fixture-net
```

- [ ] **Step 7.1: Add compose service**, **Step 7.2: Build image**

```bash
docker compose build session-cookie-lab
docker compose up -d session-cookie-lab
curl -si http://localhost:3004/httponly/missing-session | grep Set-Cookie
docker compose down session-cookie-lab
```

- [ ] **Step 7.3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(fixtures): wire session-cookie-lab into docker-compose"
```

---

## After all tasks

Run `/code-review high` on all new files, then mark Family A complete.
