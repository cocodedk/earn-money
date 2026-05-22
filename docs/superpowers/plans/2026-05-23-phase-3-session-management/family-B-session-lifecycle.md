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
| 02 | Stub 3.5 — session_fixation | `stubs/session_fixation/` |
| 03 | Stub 3.6 — no_rotation_after_login | `stubs/no_rotation_after_login/` |
| 04 | Stub 3.7 — no_invalidation_after_logout | `stubs/no_invalidation_after_logout/` |
| 05 | Stub 3.8 — long_lived_sessions | `stubs/long_lived_sessions/` |
| 06 | docker-compose wiring | `docker-compose.yml` service block |

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

## Task 02: Stub 3.5 — session_fixation

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

- [ ] **Step 2.2: Write `classify.py`**

```python
"""Stub 3.5 — Session fixation classification."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity


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
    pre_session = {
        c.name: c.value_redacted
        for c in pre_cookies if c.sensitivity != Sensitivity.LOW
    }
    if not pre_session:
        return FixationResult(status=FixationStatus.NOT_APPLICABLE, confidence="high")

    post_session = {
        c.name: c.value_redacted
        for c in post_cookies if c.sensitivity != Sensitivity.LOW
    }

    fixed = [
        name for name, pre_val in pre_session.items()
        if post_session.get(name) == pre_val
    ]
    if fixed:
        return FixationResult(
            status=FixationStatus.CONFIRMED, confidence="high", affected_names=fixed,
        )
    return FixationResult(status=FixationStatus.REJECTED, confidence="high")
```

- [ ] **Step 2.3: Write runner** — uses `submit_probe` for GET then POST, guards on
  `program.roe.allow_active_session_lifecycle_checks`

- [ ] **Step 2.4: Run all tests + commit**

```bash
cd backend && python -m pytest apps/stubs/session_fixation/ -v
git add backend/apps/stubs/session_fixation/
git commit -m "feat(stubs): 3.5 session-fixation — pre/post login session comparison"
```

---

## Task 03: Stub 3.6 — no_rotation_after_login

**Files:** `backend/apps/stubs/no_rotation_after_login/`

### Detection logic

Same as fixation but focused on session ID rotation (not the seeded-value attack):
1. GET login page → record session cookies
2. POST login → compare cookie names that existed pre-login
3. If any session-like cookie keeps the same value (fingerprint) → `CONFIRMED`

This differs from fixation in that the pre-login cookie is organically set by the server
(not seeded by the attacker). The distinction matters only for report copy.

- [ ] **Step 3.1: Write classify tests** (same structure as 3.5 but status messages differ)
- [ ] **Step 3.2: Write `classify.py`** (can import `classify_fixation` and delegate)
- [ ] **Step 3.3: Write runner + tests**
- [ ] **Step 3.4: Run + commit**

```bash
git add backend/apps/stubs/no_rotation_after_login/
git commit -m "feat(stubs): 3.6 no-rotation-after-login — session ID rotation check"
```

---

## Task 04: Stub 3.7 — no_invalidation_after_logout

**Files:** `backend/apps/stubs/no_invalidation_after_logout/`

### Detection logic

1. GET a protected resource with authenticated session → 200 (baseline)
2. POST logout
3. GET same protected resource with old session cookie → if still 200 → `CONFIRMED`
4. If 401/403 → `REJECTED`

Guard: `program.roe.allow_active_session_lifecycle_checks` must be True.

`classify.py` input: `pre_logout_status: int`, `post_logout_status: int`

- [ ] **Step 4.1: Write classify tests**:
  - 200 → 200 after logout → `CONFIRMED` / `high`
  - 200 → 401 after logout → `REJECTED` / `high`
  - 200 → 403 after logout → `REJECTED` / `high`

- [ ] **Step 4.2: Write `classify.py`**:

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
    if pre_logout_status not in range(200, 300):
        return InvalidationResult(
            status=InvalidationStatus.NOT_APPLICABLE, confidence="high",
            pre_logout_status=pre_logout_status,
            post_logout_status=post_logout_status,
        )
    if post_logout_status in range(200, 300):
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

- [ ] **Step 4.3: Write runner + tests**, **Step 4.4: Run + commit**

```bash
git add backend/apps/stubs/no_invalidation_after_logout/
git commit -m "feat(stubs): 3.7 no-invalidation-after-logout — session revocation check"
```

---

## Task 05: Stub 3.8 — long_lived_sessions

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

- [ ] **Step 5.1: Write classify tests**:
  - `Max-Age=2592000` (30d) → `CONFIRMED` / `high`
  - `Max-Age=1800` (30min) → `REJECTED` / `high`
  - No `Max-Age`, no `Expires` → `NOT_APPLICABLE`
  - `Max-Age=86400` exactly → `REJECTED` (not greater-than)
  - `Max-Age=86401` → `CONFIRMED`

- [ ] **Step 5.2: Write `classify.py`**:

```python
"""Stub 3.8 — Long-lived session detection classification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal

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
    observed_max_age: int | None


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
    age = cookie.max_age or 0
    if age > max_session_age_seconds:
        return LongLivedResult(
            status=LongLivedStatus.CONFIRMED, confidence="high",
            cookie_name=cookie.name, observed_max_age=age,
        )
    return LongLivedResult(
        status=LongLivedStatus.REJECTED, confidence="high",
        cookie_name=cookie.name, observed_max_age=age,
    )
```

- [ ] **Step 5.3: Write runner + tests**, **Step 5.4: Run + commit**

```bash
git add backend/apps/stubs/long_lived_sessions/
git commit -m "feat(stubs): 3.8 long-lived-sessions — session lifetime detection"
```

---

## Task 06: docker-compose wiring

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
