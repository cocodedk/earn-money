# Family B — Session Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `session-lifecycle-lab` fixture + stubs 3.5–3.8.

**Architecture:** Node.js fixture (`fixtures/session-lifecycle-lab/`) with stateful
in-memory session store serving login/logout/token-lifetime routes. Four stubs detect
fixation, no-rotation, no-invalidation, and long-lived sessions.

**Tech Stack:** Node 22/Express 4, Python 3.12/Django, pytest/httpx, docker-compose.

**Branch:** `feat/em-backend-phase-3-session-lifecycle` (stacked on Family A tip).

**Prerequisites:** Family A merged; shared `_shared/session/cookie_parser.py` available.

---

## Task index

| # | Task | Produces |
|---|------|---------|
| 01 | Fixture: `session-lifecycle-lab` | `fixtures/session-lifecycle-lab/` |
| 02 | Shared session lifecycle helpers | `_shared/session/session_lifecycle.py` + tests |
| 03 | Stub 3.5 — session_fixation | `stubs/session_fixation/` |
| 04 | Stub 3.6 — no_rotation_after_login | `stubs/no_rotation_after_login/` |
| 05 | Stub 3.7 — no_invalidation_after_logout | `stubs/no_invalidation_after_logout/` |
| 06 | Stub 3.8 — long_lived_sessions | `stubs/long_lived_sessions/` |
| 07 | docker-compose wiring | `docker-compose.yml` service block |

---

## Task 01: Fixture `session-lifecycle-lab`

**Files:**
- Create: `fixtures/session-lifecycle-lab/package.json`
- Create: `fixtures/session-lifecycle-lab/server.js`
- Create: `fixtures/session-lifecycle-lab/Dockerfile`

The fixture uses an in-memory session store. Each scenario is isolated.

### Key routes served

**Fixation routes** (`/fixation/*`) — fixture slug `session-lifecycle`:

| Route | Behavior |
|-------|----------|
| `/fixation/login-vulnerable` | GET → sets anon `sid`; POST login → returns same `sid` |
| `/fixation/login-rotates` | GET → sets anon `sid`; POST login → replaces `sid` |
| `/fixation/login-no-pre-cookie` | POST login → new session, no pre-cookie |
| `/fixation/cookie-seed-vulnerable` | Accepts externally set `sid`, preserves after login |
| `/fixation/cookie-seed-safe` | Replaces externally seeded `sid` on login |

**Rotation routes** (`/rotation/*`) — fixture slug `session-lifecycle`:

| Route | Behavior |
|-------|----------|
| `/rotation/login-no-rotation` | POST login → returns same session ID as pre-login |
| `/rotation/login-rotates` | POST login → new session ID |

**Invalidation routes** (`/invalidation/*`) — fixture slug `session-lifecycle`:

| Route | Behavior |
|-------|----------|
| `/invalidation/logout-keeps-session` | POST logout → session still valid |
| `/invalidation/logout-invalidates` | POST logout → session rejected (401) on reuse |
| `/invalidation/check` | GET with session → 200 if valid, 401 if not |

**Lifetime routes** (`/lifetime/*`) — fixture slug `session-token-lifetime`:

| Route | Behavior |
|-------|----------|
| `/lifetime/session-cookie-long` | Sets `sid=val; Max-Age=2592000; Path=/; Secure; HttpOnly` |
| `/lifetime/session-cookie-short` | Sets `sid=val; Max-Age=1800; Path=/; Secure; HttpOnly` |
| `/lifetime/session-cookie-browser` | Sets `sid=val; Path=/; Secure; HttpOnly` (no Max-Age/Expires) |
| `/lifetime/persistent-very-long` | Sets `sid=val; Max-Age=31536000; Path=/; Secure; HttpOnly` |

- [ ] **Step 1.1: Write `package.json`**

```json
{
  "name": "session-lifecycle-lab",
  "version": "0.1.0",
  "description": "Stateful session-lifecycle fixture for Phase-3 stubs 3.5-3.8.",
  "main": "server.js",
  "private": true,
  "scripts": { "start": "node server.js" },
  "dependencies": { "express": "4.21.2" },
  "license": "MIT"
}
```

- [ ] **Step 1.2: Write `server.js`** (~180 lines covering all routes above with in-memory session map)

Key implementation notes:
- `sessions = new Map()` — maps token → `{authenticated, created_at}`
- Fixation: `/fixation/login-vulnerable` GET sets `sid=<token>` and stores it; POST `/login`
  with `Content-Type: application/x-www-form-urlencoded` body `username=user&password=pass`
  authenticates without rotating
- Rotation: `/rotation/login-rotates` POST deletes old session, creates new one
- Invalidation: `/invalidation/logout-keeps-session` POST sets `authenticated=false` in session
  but keeps the `sid` cookie valid; `/invalidation/check` reads the cookie and returns 200 if
  session exists
- Lifetime: static `Set-Cookie` header responses

- [ ] **Step 1.3: Write `Dockerfile`** (same pattern as session-cookie-lab)

- [ ] **Step 1.4: Install + smoke-test**

```bash
cd fixtures/session-lifecycle-lab && npm install && node server.js &
sleep 1
# Check fixation — GET sets anon cookie
curl -c /tmp/jar.txt -si http://localhost:3000/fixation/login-vulnerable | grep Set-Cookie
# POST login with same jar — should keep same sid
curl -b /tmp/jar.txt -c /tmp/jar2.txt -si -X POST \
  -d "username=user&password=pass" http://localhost:3000/fixation/login
# Compare sids
kill %1
```

- [ ] **Step 1.5: Commit fixture**

```bash
git add fixtures/session-lifecycle-lab/
git commit -m "feat(fixtures): session-lifecycle-lab — lifecycle routes for stubs 3.5-3.8"
```

---

## Task 02: Shared session lifecycle helpers

**Files:**
- Create: `backend/apps/stubs/_shared/session/session_lifecycle.py`
- Create: `backend/apps/stubs/_shared/session/tests/test_session_lifecycle.py`

Both stubs 3.5 and 3.6 need the same pre/post cookie comparison logic. Lifting it to shared avoids a cross-stub import anti-pattern.

- [ ] **Step 2.1: Write failing tests**

```python
"""Tests for shared session lifecycle comparison helpers."""
from __future__ import annotations
from apps.stubs._shared.session.cookie_parser import parse_set_cookie
from apps.stubs._shared.session.session_lifecycle import compare_session_cookies, CompareResult


def _c(header):
    return parse_set_cookie(header)


def test_same_value_is_fixed():
    pre = [_c("sid=x; Path=/")]
    post = [_c("sid=x; Path=/")]
    r = compare_session_cookies(pre, post)
    assert r.fixed_names == ["sid"]


def test_different_value_not_fixed():
    pre = [_c("sid=x; Path=/")]
    post = [_c("sid=y; Path=/")]
    r = compare_session_cookies(pre, post)
    assert r.fixed_names == []


def test_no_pre_cookie_empty_fixed():
    r = compare_session_cookies([], [_c("sid=x; Path=/")])
    assert r.no_pre_cookie is True


def test_none_value_skipped():
    # cookie with no value at all should not trigger a false positive
    pre = [_c("sid")]
    post = [_c("sid")]
    r = compare_session_cookies(pre, post)
    assert r.fixed_names == []
```

- [ ] **Step 2.2: Implement `session_lifecycle.py`**

```python
"""Shared pre/post login session-cookie comparison for stubs 3.5 and 3.6."""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity


@dataclass(frozen=True)
class CompareResult:
    fixed_names: list[str]
    no_pre_cookie: bool


def compare_session_cookies(
    pre_cookies: list[ParsedCookie],
    post_cookies: list[ParsedCookie],
) -> CompareResult:
    pre_session = {
        c.name: c.value_redacted
        for c in pre_cookies
        if c.sensitivity != Sensitivity.LOW and c.value_redacted is not None
    }
    if not pre_session:
        return CompareResult(fixed_names=[], no_pre_cookie=True)

    post_session = {
        c.name: c.value_redacted
        for c in post_cookies
        if c.sensitivity != Sensitivity.LOW and c.value_redacted is not None
    }

    fixed = [
        name for name, pre_val in pre_session.items()
        if post_session.get(name) == pre_val
    ]
    return CompareResult(fixed_names=fixed, no_pre_cookie=False)
```

- [ ] **Step 2.3: Run tests + commit**

```bash
cd backend && python -m pytest apps/stubs/_shared/session/tests/test_session_lifecycle.py -v
git add backend/apps/stubs/_shared/session/
git commit -m "feat(session): shared session lifecycle helper — pre/post cookie comparison"
```

---

## Task 03: Stub 3.5 — session_fixation

**Files:**
- Create: `backend/apps/stubs/session_fixation/__init__.py`
- Create: `backend/apps/stubs/session_fixation/classify.py`
- Create: `backend/apps/stubs/session_fixation/runner.py`
- Create: `backend/apps/stubs/session_fixation/tests/`

### Detection logic

1. GET login page → record `Set-Cookie` session-like cookies (pre-login fingerprints)
2. POST login with test credentials → record post-login cookies
3. Compare fingerprints: same name + same value hash → `CONFIRMED` / `high`
4. Same name + different value → `REJECTED` (rotation happened)
5. No pre-login cookie → `NOT_APPLICABLE` (can't prove fixation)

`classify.py` input: `pre_cookies: list[ParsedCookie]`, `post_cookies: list[ParsedCookie]`
Returns: `FixationResult` with `status`, `confidence`, `affected_names: list[str]`

- [ ] **Step 2.1: Write failing tests** covering:
  - Same `sid` hash before/after → `CONFIRMED`
  - Different `sid` hash before/after → `REJECTED`
  - No pre-cookie → `NOT_APPLICABLE`
  - Non-session cookies ignored

- [ ] **Step 3.2: Write `classify.py`**

```python
"""Stub 3.5 — Session fixation classification."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from apps.stubs._shared.session.cookie_parser import ParsedCookie
from apps.stubs._shared.session.session_lifecycle import compare_session_cookies


class FixationStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class FixationResult:
    status: FixationStatus
    confidence: Literal["low", "medium", "high"]
    affected_names: list[str] = field(default_factory=list)


def classify_fixation(
    pre_cookies: list[ParsedCookie],
    post_cookies: list[ParsedCookie],
) -> FixationResult:
    result = compare_session_cookies(pre_cookies, post_cookies)
    if result.no_pre_cookie:
        return FixationResult(status=FixationStatus.NOT_APPLICABLE, confidence="high")
    if result.fixed_names:
        return FixationResult(
            status=FixationStatus.CONFIRMED, confidence="high",
            affected_names=result.fixed_names,
        )
    return FixationResult(status=FixationStatus.REJECTED, confidence="high")
```

- [ ] **Step 3.3: Write runner** — uses `submit_probe` for GET then POST, guards on
  `program.roe.allow_active_session_lifecycle_checks`.
  **Critical:** if GET returns `None`, skip the POST entirely (no pre-cookie fingerprint
  to compare against). Pattern: `get_resp = submit_probe(get_req); if get_resp is None: return`

- [ ] **Step 3.4: Run all tests + commit**

```bash
cd backend && python -m pytest apps/stubs/session_fixation/ -v
git add backend/apps/stubs/session_fixation/
git commit -m "feat(stubs): 3.5 session-fixation — pre/post login session comparison"
```

---

## Task 04: Stub 3.6 — no_rotation_after_login

**Files:** `backend/apps/stubs/no_rotation_after_login/`

### Detection logic

Same as fixation but focused on session ID rotation (not the seeded-value attack):
1. GET login page → record session cookies
2. POST login → compare cookie names that existed pre-login
3. If any session-like cookie keeps the same value (fingerprint) → `CONFIRMED`

This differs from fixation in that the pre-login cookie is organically set by the server
(not seeded by the attacker). The distinction matters only for report copy.

- [ ] **Step 4.1: Write classify tests** (same structure as 3.5 but distinct status type/messages)
- [ ] **Step 4.2: Write `classify.py`** — import `compare_session_cookies` from
  `_shared/session/session_lifecycle` (NOT from stub 3.5; stubs must not import each other)
- [ ] **Step 4.3: Write runner + tests**
- [ ] **Step 4.4: Run + commit**

```bash
git add backend/apps/stubs/no_rotation_after_login/
git commit -m "feat(stubs): 3.6 no-rotation-after-login — session ID rotation check"
```

---

## Task 05: Stub 3.7 — no_invalidation_after_logout

**Files:** `backend/apps/stubs/no_invalidation_after_logout/`

### Detection logic

1. GET a protected resource with authenticated session → 200 (baseline)
2. POST logout
3. GET same protected resource with old session cookie → if still 200 → `CONFIRMED`
4. If 401/403 → `REJECTED`

Guard: `program.roe.allow_active_session_lifecycle_checks` must be True.

`classify.py` input: `pre_logout_status: int`, `post_logout_status: int`

- [ ] **Step 5.1: Write classify tests**:
  - 200 → 200 after logout → `CONFIRMED` / `high`
  - 200 → 401 after logout → `REJECTED` / `high`
  - 200 → 403 after logout → `REJECTED` / `high`

- [ ] **Step 5.2: Write `classify.py`**:

```python
"""Stub 3.7 — No session invalidation after logout classification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class InvalidationStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class InvalidationResult:
    status: InvalidationStatus
    confidence: Literal["low", "medium", "high"]
    pre_logout_status: int
    post_logout_status: int


def classify_invalidation(
    pre_logout_status: int, post_logout_status: int,
) -> InvalidationResult:
    if not (200 <= pre_logout_status < 300):
        return InvalidationResult(
            status=InvalidationStatus.NOT_APPLICABLE, confidence="high",
            pre_logout_status=pre_logout_status,
            post_logout_status=post_logout_status,
        )
    if 200 <= post_logout_status < 300:
        return InvalidationResult(
            status=InvalidationStatus.CONFIRMED, confidence="high",
            pre_logout_status=pre_logout_status,
            post_logout_status=post_logout_status,
        )
    return InvalidationResult(
        status=InvalidationStatus.REJECTED, confidence="high",
        pre_logout_status=pre_logout_status,
        post_logout_status=post_logout_status,
    )
```

- [ ] **Step 5.3: Write runner + tests**, **Step 5.4: Run + commit**

```bash
git add backend/apps/stubs/no_invalidation_after_logout/
git commit -m "feat(stubs): 3.7 no-invalidation-after-logout — session revocation check"
```

---

## Task 06: Stub 3.8 — long_lived_sessions

**Files:** `backend/apps/stubs/long_lived_sessions/`

Fixture slug: `session-token-lifetime`.

### Detection logic (passive, cookie attribute inspection)

1. Collect `Set-Cookie` headers from target base URL.
2. For session-like cookies, check `Max-Age` and `Expires`:
   - `Max-Age > threshold_seconds` → `CONFIRMED` / `high`
   - `Expires` far in the future → `CONFIRMED` / `high`
   - No `Max-Age`/`Expires` (session cookie) → `NOT_APPLICABLE` (browser-session lifetime)
   - `Max-Age <= threshold_seconds` → `REJECTED`

Default threshold: 86400 seconds (24 hours). Configurable via `max_session_age_seconds`.

`classify.py` input: `ParsedCookie`, `max_session_age_seconds: int = 86400`

- [ ] **Step 6.1: Write classify tests**:
  - `Max-Age=2592000` (30d) → `CONFIRMED` / `high`
  - `Max-Age=1800` (30min) → `REJECTED` / `high`
  - No `Max-Age`, no `Expires` → `NOT_APPLICABLE`
  - `Max-Age=86400` exactly → `REJECTED` (not greater-than)
  - `Max-Age=86401` → `CONFIRMED`
  - Only `Expires` set to far future → `CONFIRMED` (verify Expires-only path works)

- [ ] **Step 6.2: Write `classify.py`**:

```python
"""Stub 3.8 — Long-lived session detection classification."""
from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Literal, Optional

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity

_DEFAULT_MAX_AGE = 86400  # seconds


class LongLivedStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class LongLivedResult:
    status: LongLivedStatus
    confidence: Literal["low", "medium", "high"]
    cookie_name: str
    observed_max_age: Optional[int]


def classify_cookie(
    cookie: ParsedCookie,
    max_session_age_seconds: int = _DEFAULT_MAX_AGE,
) -> LongLivedResult:
    if cookie.sensitivity == Sensitivity.LOW:
        return LongLivedResult(
            status=LongLivedStatus.NOT_APPLICABLE, confidence="high",
            cookie_name=cookie.name, observed_max_age=None,
        )
    if cookie.max_age is None and cookie.expires is None:
        return LongLivedResult(
            status=LongLivedStatus.NOT_APPLICABLE, confidence="low",
            cookie_name=cookie.name, observed_max_age=None,
        )
    # Max-Age takes precedence; fall back to Expires if absent
    if cookie.max_age is not None:
        age = cookie.max_age
    else:
        age = _expires_to_seconds(cookie.expires)
    if age is None:
        return LongLivedResult(
            status=LongLivedStatus.NOT_APPLICABLE, confidence="low",
            cookie_name=cookie.name, observed_max_age=None,
        )
    if age > max_session_age_seconds:
        return LongLivedResult(
            status=LongLivedStatus.CONFIRMED, confidence="high",
            cookie_name=cookie.name, observed_max_age=age,
        )
    return LongLivedResult(
        status=LongLivedStatus.REJECTED, confidence="high",
        cookie_name=cookie.name, observed_max_age=age,
    )


def _expires_to_seconds(expires: Optional[str]) -> Optional[int]:
    if not expires:
        return None
    try:
        import datetime
        dt = parsedate_to_datetime(expires)
        remaining = int((dt - datetime.datetime.now(tz=datetime.timezone.utc)).total_seconds())
        return max(remaining, 0)
    except Exception:
        return None
```

- [ ] **Step 6.3: Write runner + tests**, **Step 6.4: Run + commit**

```bash
git add backend/apps/stubs/long_lived_sessions/
git commit -m "feat(stubs): 3.8 long-lived-sessions — session lifetime detection"
```

---

## Task 07: docker-compose wiring

```yaml
  session-lifecycle-lab:
    build: ./fixtures/session-lifecycle-lab
    image: earnmoney-session-lifecycle-lab:dev
    ports:
      - "3005:3000"
    networks:
      - fixture-net
```

```bash
docker compose build session-lifecycle-lab
git add docker-compose.yml
git commit -m "feat(fixtures): wire session-lifecycle-lab into docker-compose"
```

---

## After all tasks

Run `/code-review high` on Family B files, then open PR against Family A tip.
