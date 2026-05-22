# Family C — JWT/Tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `jwt-session-lab` fixture + stubs 3.9–3.13.

**Architecture:** Node.js fixture (`fixtures/jwt-session-lab/`) issues real JWTs via
`jsonwebtoken`. Stubs inspect token headers/claims passively; active probes (algorithm
confusion, forged tokens) are gated by `allow_*` knobs defaulting to `false`.

**Tech Stack:** Node 22/Express 4 + jsonwebtoken, Python 3.12/Django, pytest/httpx.

**Branch:** `feat/em-backend-phase-3-jwt-tokens` (stacked on Family B tip).

**Prerequisites:** Family B merged; `_shared/session/cookie_parser.py` available.

---

## Task index

| # | Task | Produces |
|---|------|---------|
| 01 | Fixture: `jwt-session-lab` | `fixtures/jwt-session-lab/` |
| 02 | Shared JWT decoder | `_shared/session/jwt_decoder.py` + tests |
| 03 | Stub 3.9 — jwt_algorithm_confusion | `stubs/jwt_algorithm_confusion/` |
| 04 | Stub 3.10 — weak_signing_keys | `stubs/weak_signing_keys/` |
| 05 | Stub 3.11 — missing_expiry | `stubs/missing_expiry/` |
| 06 | Stub 3.12 — token_accepted_after_logout | `stubs/token_accepted_after_logout/` |
| 07 | Stub 3.13 — refresh_token_abuse | `stubs/refresh_token_abuse/` |
| 08 | docker-compose wiring | `docker-compose.yml` service block |

---

## Task 01: Fixture `jwt-session-lab`

**Files:**
- Create: `fixtures/jwt-session-lab/package.json`
- Create: `fixtures/jwt-session-lab/server.js`
- Create: `fixtures/jwt-session-lab/Dockerfile`

### Key routes served

**Algorithm confusion** (`/alg/*`):

| Route | Behavior |
|-------|----------|
| `/alg/get-token` | Issues RS256 JWT with `sub=testuser` |
| `/alg/verify` | Accepts any JWT; vulnerable version accepts `alg=none` |
| `/alg/verify-strict` | Rejects `alg=none` and HS256 tokens |

**Weak key** (`/key/*`):

| Route | Behavior |
|-------|----------|
| `/key/get-token-weak` | Issues HS256 JWT signed with `secret` |
| `/key/get-token-strong` | Issues HS256 JWT signed with 64-byte random key |
| `/key/verify` | Returns 200 if token valid, 401 otherwise |

**Missing expiry** (`/expiry/*`):

| Route | Behavior |
|-------|----------|
| `/expiry/no-exp` | Issues JWT without `exp` claim |
| `/expiry/with-exp` | Issues JWT with `exp = now + 3600` |
| `/expiry/expired` | Issues JWT with `exp` in the past |

**Token reuse after logout** (`/reuse/*`):

| Route | Behavior |
|-------|----------|
| `/reuse/login` | POST → issues `access_token` JWT, adds JTI to `validJtis` set |
| `/reuse/profile` | GET with Bearer → 200 if JTI in `validJtis`, 401 otherwise |
| `/reuse/logout` | POST with Bearer → removes JTI from `validJtis` |
| `/reuse/profile-no-revoke` | GET with Bearer → 200 regardless of logout (vulnerable) |

**Refresh abuse** (`/refresh/*`):

| Route | Behavior |
|-------|----------|
| `/refresh/login` | POST → issues `access_token` + `refresh_token` (both JWTs) |
| `/refresh/refresh-no-rotate` | POST with old refresh → issues new access, keeps old refresh valid |
| `/refresh/refresh-rotate` | POST with old refresh → issues new access + new refresh, old refresh rejected |

- [ ] **Step 1.1: Write `package.json`**

```json
{
  "name": "jwt-session-lab",
  "version": "0.1.0",
  "description": "JWT fixture for Phase-3 stubs 3.9-3.13.",
  "main": "server.js",
  "private": true,
  "scripts": { "start": "node server.js" },
  "dependencies": { "express": "4.21.2", "jsonwebtoken": "9.0.2" },
  "license": "MIT"
}
```

- [ ] **Step 1.2: Write `server.js`** (~180 lines)

Key implementation notes:
- Use `jsonwebtoken` npm package to sign/verify tokens
- Algorithm confusion: `jwt.sign(payload, WEAK_SECRET, { algorithm: 'HS256' })`;
  the vulnerable `/alg/verify` does `jwt.decode()` without verify + trusts the `alg` header
- Weak key: `WEAK_SECRET = 'secret'`; strong key: `crypto.randomBytes(64).toString('hex')`
  (generated once at startup)
- JTI revocation: `const validJtis = new Set()`, add on login, delete on logout

- [ ] **Step 1.3: `Dockerfile`**, **Step 1.4: npm install + smoke test**, **Step 1.5: commit**

```bash
git add fixtures/jwt-session-lab/
git commit -m "feat(fixtures): jwt-session-lab — JWT weakness routes for stubs 3.9-3.13"
```

---

## Task 02: Shared JWT decoder

**Files:**
- Create: `backend/apps/stubs/_shared/session/jwt_decoder.py`
- Create: `backend/apps/stubs/_shared/session/tests/test_jwt_decoder.py`

This is a **passive** decoder — it never verifies signatures. It decodes header and
payload from a raw JWT string without any key.

- [ ] **Step 2.1: Write failing tests**

```python
"""Tests for shared JWT decoder."""
from __future__ import annotations
import base64, json
import pytest
from apps.stubs._shared.session.jwt_decoder import decode_jwt_unsafe, JwtClaims


def _make_jwt(header: dict, payload: dict) -> str:
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{b64(header)}.{b64(payload)}.fakesig"


def test_decodes_alg_and_kid():
    token = _make_jwt({"alg": "RS256", "typ": "JWT"}, {"sub": "u1", "exp": 9999999999})
    c = decode_jwt_unsafe(token)
    assert c.alg == "RS256"
    assert c.exp == 9999999999


def test_alg_none_detected():
    token = _make_jwt({"alg": "none"}, {"sub": "u1"})
    c = decode_jwt_unsafe(token)
    assert c.alg_is_none is True


def test_missing_exp():
    token = _make_jwt({"alg": "HS256"}, {"sub": "u1"})
    c = decode_jwt_unsafe(token)
    assert c.exp is None


def test_bad_token_returns_none():
    assert decode_jwt_unsafe("not.a.jwt") is None
    assert decode_jwt_unsafe("") is None
    assert decode_jwt_unsafe("only.two") is None


def test_token_value_not_in_repr():
    token = _make_jwt({"alg": "HS256"}, {"sub": "u1"})
    c = decode_jwt_unsafe(token)
    assert token not in str(c)
```

- [ ] **Step 2.2: Implement `jwt_decoder.py`**

```python
"""Passive JWT decoder — inspects header+payload without signature verification."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class JwtClaims:
    alg: Optional[str]
    typ: Optional[str]
    kid: Optional[str]
    sub: Optional[str]
    exp: Optional[int]
    iat: Optional[int]
    jti: Optional[str]
    iss: Optional[str]
    extra_claims: dict[str, Any]

    @property
    def alg_is_none(self) -> bool:
        return (self.alg or "").lower() == "none"

    @property
    def exp_missing(self) -> bool:
        return self.exp is None


def decode_jwt_unsafe(token: str) -> Optional[JwtClaims]:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        header = _b64decode(parts[0])
        payload = _b64decode(parts[1])
    except Exception:
        return None

    known = {"sub", "exp", "iat", "jti", "iss"}
    extra = {k: v for k, v in payload.items() if k not in known}

    return JwtClaims(
        alg=header.get("alg"),
        typ=header.get("typ"),
        kid=header.get("kid"),
        sub=payload.get("sub"),
        exp=payload.get("exp"),
        iat=payload.get("iat"),
        jti=payload.get("jti"),
        iss=payload.get("iss"),
        extra_claims=extra,
    )


def _b64decode(s: str) -> dict:
    padded = s + "=" * (-len(s) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))
```

- [ ] **Step 2.3: Run tests + commit**

```bash
cd backend && python -m pytest apps/stubs/_shared/session/tests/test_jwt_decoder.py -v
git add backend/apps/stubs/_shared/session/jwt_decoder.py \
        backend/apps/stubs/_shared/session/tests/test_jwt_decoder.py
git commit -m "feat(session): shared JWT decoder — passive header+payload inspection"
```

---

## Task 03: Stub 3.9 — jwt_algorithm_confusion

**Files:** `backend/apps/stubs/jwt_algorithm_confusion/`

### Detection logic (passive default)

1. Collect JWT-bearing responses (cookie, `Authorization` header hint, JSON `access_token`)
2. Decode without verification via `decode_jwt_unsafe`
3. If `alg == "none"` or `alg in ("", None)` → `CONFIRMED` / `high`
4. If `alg in ("HS256", "HS384", "HS512")` and issuer suggests asymmetric expected →
   `CANDIDATE` / `medium`

Active probe (only when `allow_modified_token_submission=True`):
5. Replace `alg=none` + remove signature → submit to verify endpoint → if 200 → `CONFIRMED`

`classify.py` input: `JwtClaims`, `expected_alg: str | None = None`

- [ ] **Step 3.1: Write failing classify tests** covering: `alg=none` → CONFIRMED,
  RS256 → NOT_APPLICABLE (no confusion detected passively), HS256 with RS expected → CANDIDATE
- [ ] **Step 3.2: Write `classify.py`**
- [ ] **Step 3.3: Write runner + tests** (passive mode only; active probe tests use mock)
- [ ] **Step 3.4: Run + commit**

```bash
git add backend/apps/stubs/jwt_algorithm_confusion/
git commit -m "feat(stubs): 3.9 jwt-algorithm-confusion — alg header inspection"
```

---

## Task 04: Stub 3.10 — weak_signing_keys

**Files:** `backend/apps/stubs/weak_signing_keys/`

### Detection logic (offline HMAC brute-force)

1. Collect HMAC-signed JWT from target
2. Attempt HMAC verification against a wordlist of weak secrets:
   `["secret", "password", "1234", "jwt", "key", "mysecret", "supersecret",
     "changeme", "admin", "test", "", "none", "123456", "letmein"]`
3. First match → `CONFIRMED` / `high` with the redacted-secret fingerprint
4. No match → `REJECTED` / `high`

⚠ Offline only — no network requests needed for the key check itself.

`classify.py` input: `raw_token: str`, `wordlist: list[str]`
Returns: `WeakKeyResult` with `status`, `matched_secret_fingerprint: str | None`

- [ ] **Step 4.1: Write failing classify tests** (pure unit, no HTTP)
- [ ] **Step 4.2: Write `classify.py`** using `hmac.new` or `jwt` PyPI package for verify
  — use stdlib `hmac` + manual base64 to avoid adding a new dependency
- [ ] **Step 4.3: Write runner + tests**
- [ ] **Step 4.4: Run + commit**

```bash
git add backend/apps/stubs/weak_signing_keys/
git commit -m "feat(stubs): 3.10 weak-signing-keys — HMAC wordlist check"
```

---

## Task 05: Stub 3.11 — missing_expiry

**Files:** `backend/apps/stubs/missing_expiry/`

### Detection logic (passive)

1. Collect JWTs from response headers/cookies/JSON
2. Decode with `decode_jwt_unsafe`
3. If `exp` claim missing → `CONFIRMED` / `high` (per spec: `treat_missing_exp_as_confirmed=true`)
4. If `exp` present → `REJECTED` / `high`

`classify.py` input: `JwtClaims` → `MissingExpiryResult`

- [ ] **Step 5.1: Failing tests**, **Step 5.2: classify.py**, **Step 5.3: runner + tests**
- [ ] **Step 5.4: Run + commit**

```bash
git add backend/apps/stubs/missing_expiry/
git commit -m "feat(stubs): 3.11 missing-expiry — JWT exp claim check"
```

---

## Task 06: Stub 3.12 — token_accepted_after_logout

**Files:** `backend/apps/stubs/token_accepted_after_logout/`

Guard: `allow_access_token_reuse_check = False` by default.

### Detection logic (active, requires gate)

1. Login → capture access token
2. Access protected resource → confirm 200
3. Logout
4. Replay same access token to protected resource
5. If 200 again → `CONFIRMED` / `high`; if 401/403 → `REJECTED` / `high`

`classify.py` input: `post_logout_status: int`

- [ ] **Step 6.1: Failing tests**, **Step 6.2: classify.py**, **Step 6.3: runner + tests**
  (including test that guard prevents execution when flag is False)
- [ ] **Step 6.4: Run + commit**

```bash
git add backend/apps/stubs/token_accepted_after_logout/
git commit -m "feat(stubs): 3.12 token-accepted-after-logout — JTI revocation check"
```

---

## Task 07: Stub 3.13 — refresh_token_abuse

**Files:** `backend/apps/stubs/refresh_token_abuse/`

Guard: `allow_old_refresh_reuse_check = False` by default.

### Detection logic

1. Login → capture refresh token
2. Use refresh token once → get new access token
3. Replay original refresh token again
4. If second use succeeds → `CONFIRMED` / `high` (no rotation/revocation)
5. If second use fails → `REJECTED` / `high`

`classify.py` input: `first_use_status: int`, `second_use_status: int`

- [ ] **Step 7.1: Failing tests**, **Step 7.2: classify.py**, **Step 7.3: runner + tests**
- [ ] **Step 7.4: Run + commit**

```bash
git add backend/apps/stubs/refresh_token_abuse/
git commit -m "feat(stubs): 3.13 refresh-token-abuse — refresh reuse detection"
```

---

## Task 08: docker-compose wiring

```yaml
  jwt-session-lab:
    build: ./fixtures/jwt-session-lab
    image: earnmoney-jwt-session-lab:dev
    ports:
      - "3006:3000"
    networks:
      - fixture-net
```

```bash
git add docker-compose.yml
git commit -m "feat(fixtures): wire jwt-session-lab into docker-compose"
```

---

## After all tasks

Run `/code-review high` on Family C files, then open PR against Family B tip.
