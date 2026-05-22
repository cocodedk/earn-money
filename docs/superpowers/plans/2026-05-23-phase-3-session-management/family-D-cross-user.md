# Family D — Cross-User Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `session-cross-user-lab` fixture + stubs 3.14–3.16.

**Architecture:** Node.js fixture (`fixtures/session-cross-user-lab/`) manages two
concurrent user sessions. Stubs detect session mix-up, cached private data exposure,
and concurrent session weakness.

**Tech Stack:** Node 22/Express 4, Python 3.12/Django, pytest/httpx, docker-compose.

**Branch:** `feat/em-backend-phase-3-cross-user` (stacked on Family C tip).

**Prerequisites:** Family C merged; shared cookie parser + JWT decoder available.

---

## Task index

| # | Task | Produces |
|---|------|---------|
| 01 | Fixture: `session-cross-user-lab` | `fixtures/session-cross-user-lab/` |
| 02 | Stub 3.14 — session_mix_up | `stubs/session_mix_up/` |
| 03 | Stub 3.15 — cached_private_data | `stubs/cached_private_data/` |
| 04 | Stub 3.16 — concurrent_session_weakness | `stubs/concurrent_session_weakness/` |
| 05 | docker-compose wiring | `docker-compose.yml` service block |

---

## Task 01: Fixture `session-cross-user-lab`

**Files:**
- Create: `fixtures/session-cross-user-lab/package.json`
- Create: `fixtures/session-cross-user-lab/server.js`
- Create: `fixtures/session-cross-user-lab/Dockerfile`

### Key routes served — fixture slug `session-cross-user`

**Session mix-up** (`/mixup/*`):

| Route | Behavior |
|-------|----------|
| `/mixup/login` | POST `username+password` → sets `sid`; stores `{user, private_data}` |
| `/mixup/profile` | GET with `sid` → returns `{user, private_data}` for that session |
| `/mixup/cross-reuse` | GET with user-A `sid` → returns user-B profile (vulnerable) |
| `/mixup/cross-safe` | GET with user-A `sid` → returns user-A profile or 403 (safe) |

**Cached private data** (`/cache/*`):

| Route | Behavior |
|-------|----------|
| `/cache/private` | GET → returns private JSON with `Cache-Control: public, max-age=3600` (vulnerable) |
| `/cache/private-safe` | GET → returns private JSON with `Cache-Control: no-store` (safe) |
| `/cache/public-resource` | GET → returns public JSON with `Cache-Control: public, max-age=3600` (normal) |
| `/cache/private-logged-out` | GET after logout → still returns cached private data (vulnerable) |

**Concurrent sessions** (`/concurrent/*`):

| Route | Behavior |
|-------|----------|
| `/concurrent/login` | POST → allows multiple sessions per user (stores in `sessions[user][]`) |
| `/concurrent/sessions` | GET with session → returns count of active sessions for user |
| `/concurrent/logout-all` | POST → removes all sessions for user from map |
| `/concurrent/logout-all-broken` | POST → only removes current session (others survive) |
| `/concurrent/profile` | GET with session → 200 if session valid |

- [ ] **Step 1.1: Write `package.json`**

```json
{
  "name": "session-cross-user-lab",
  "version": "0.1.0",
  "description": "Cross-user session fixture for Phase-3 stubs 3.14-3.16.",
  "main": "server.js",
  "private": true,
  "scripts": { "start": "node server.js" },
  "dependencies": { "express": "4.21.2" },
  "license": "MIT"
}
```

- [ ] **Step 1.2: Write `server.js`** (~170 lines)

Key implementation notes:
- `users = { alice: { password: 'alice123', private: 'Alice private data' }, ... }`
- `sessions = new Map()` — maps `token → { user, created_at }`
- Mix-up: `/mixup/cross-reuse` always returns alice's profile regardless of `sid` (simulates bug)
- Cache: private route sets `Cache-Control: public, max-age=3600` (intentional vulnerability)
- Concurrent: `userSessions = new Map()` where each user maps to a `Set` of tokens;
  `/concurrent/logout-all-broken` only deletes the requesting token, not all

- [ ] **Step 1.3: `Dockerfile`**, **Step 1.4: npm install + smoke test**, **Step 1.5: commit**

```bash
git add fixtures/session-cross-user-lab/
git commit -m "feat(fixtures): session-cross-user-lab — cross-user session routes 3.14-3.16"
```

---

## Task 02: Stub 3.14 — session_mix_up

**Files:** `backend/apps/stubs/session_mix_up/`

### Detection logic

This stub requires two separate authenticated contexts (user-A and user-B). It can only
run against fixture targets with `allow_cross_user_probes = True`.

1. Login as user-A → capture session token A
2. Login as user-B → capture session token B
3. Use token-A to access user-B's protected resource
4. If response contains user-B's private data → `CONFIRMED` / `high`
5. If 403/404 → `REJECTED` / `high`

Guard: `program.roe.allow_cross_user_probes = True` required.

`classify.py` input: `user_a_data: dict`, `user_b_data: dict`, `cross_response_data: dict`
Returns: `MixUpResult` with `status`, `confidence`, `leaked_user: str | None`

Key check: if `cross_response_data` contains keys/values from `user_b_data` when accessed
with token-A, it's a mix-up.

- [ ] **Step 2.1: Write failing classify tests**:
  - Response data matches user-B → `CONFIRMED` / `high`
  - 403 status → `REJECTED` / `high`
  - Response data matches user-A (correct user) → `REJECTED` / `high`

- [ ] **Step 2.2: Write `classify.py`**:

```python
"""Stub 3.14 — Session mix-up classification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Optional


class MixUpStatus(str, Enum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class MixUpResult:
    status: MixUpStatus
    confidence: Literal["low", "medium", "high"]
    leaked_user: Optional[str]


def classify_mix_up(
    user_a_id: str,
    user_b_id: str,
    cross_response_body: str,
    cross_response_status: int,
) -> MixUpResult:
    if cross_response_status in (401, 403, 404):
        return MixUpResult(status=MixUpStatus.REJECTED, confidence="high", leaked_user=None)
    if user_b_id in cross_response_body and user_a_id not in cross_response_body:
        return MixUpResult(
            status=MixUpStatus.CONFIRMED, confidence="high", leaked_user=user_b_id,
        )
    return MixUpResult(status=MixUpStatus.REJECTED, confidence="high", leaked_user=None)
```

- [ ] **Step 2.3: Write runner + tests**, **Step 2.4: Run + commit**

```bash
git add backend/apps/stubs/session_mix_up/
git commit -m "feat(stubs): 3.14 session-mix-up — cross-user data leak detection"
```

---

## Task 03: Stub 3.15 — cached_private_data

**Files:** `backend/apps/stubs/cached_private_data/`

### Detection logic (passive, header inspection)

1. GET authenticated resource → check `Cache-Control` and `Pragma` headers
2. Flags:
   - No `Cache-Control` → `CANDIDATE` / `medium`
   - `Cache-Control: public` or missing `no-store`/`no-cache` on private resource → `CONFIRMED`
   - `Cache-Control: no-store` → `REJECTED`
   - `Cache-Control: private` without `no-store` → `CANDIDATE` / `low`

Classification uses response status + auth context to determine if resource is private.

`classify.py` input: `cache_header: str | None`, `is_authenticated_resource: bool`

- [ ] **Step 3.1: Write failing classify tests**:
  - No `Cache-Control` on auth resource → `CANDIDATE`
  - `Cache-Control: public, max-age=3600` on auth resource → `CONFIRMED` / `high`
  - `Cache-Control: no-store` → `REJECTED` / `high`
  - `Cache-Control: private, max-age=3600` (no no-store) → `CANDIDATE` / `low`
  - Public resource `Cache-Control: public` → `NOT_APPLICABLE`

- [ ] **Step 3.2: Write `classify.py`**:

```python
"""Stub 3.15 — Cached private data classification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional


class CachedDataStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class CachedDataResult:
    status: CachedDataStatus
    confidence: Literal["low", "medium", "high"]
    cache_header: Optional[str]
    weakness_kind: Optional[str]


def classify_cache(
    cache_header: Optional[str], *, is_authenticated_resource: bool,
) -> CachedDataResult:
    if not is_authenticated_resource:
        return CachedDataResult(
            status=CachedDataStatus.NOT_APPLICABLE, confidence="high",
            cache_header=cache_header, weakness_kind=None,
        )
    if cache_header is None:
        return CachedDataResult(
            status=CachedDataStatus.CANDIDATE, confidence="medium",
            cache_header=None, weakness_kind="missing_cache_control",
        )
    lower = cache_header.lower()
    if "no-store" in lower:
        return CachedDataResult(
            status=CachedDataStatus.REJECTED, confidence="high",
            cache_header=cache_header, weakness_kind=None,
        )
    if "public" in lower:
        return CachedDataResult(
            status=CachedDataStatus.CONFIRMED, confidence="high",
            cache_header=cache_header, weakness_kind="public_cache_on_private_resource",
        )
    if "private" in lower:
        return CachedDataResult(
            status=CachedDataStatus.CANDIDATE, confidence="low",
            cache_header=cache_header, weakness_kind="private_without_no_store",
        )
    return CachedDataResult(
        status=CachedDataStatus.CANDIDATE, confidence="medium",
        cache_header=cache_header, weakness_kind="missing_no_store",
    )
```

- [ ] **Step 3.3: Write runner + tests**, **Step 3.4: Run + commit**

```bash
git add backend/apps/stubs/cached_private_data/
git commit -m "feat(stubs): 3.15 cached-private-data — response cache header inspection"
```

---

## Task 04: Stub 3.16 — concurrent_session_weakness

**Files:** `backend/apps/stubs/concurrent_session_weakness/`

Guard: `program.roe.allow_concurrent_session_probes = True` required.

### Detection logic

Behaviour depends on `concurrent_session_policy` config knob (default `"unknown"`):

- `"unknown"` → only report if fixture explicitly signals a violation; otherwise `CANDIDATE`
- `"single_session"` → if second login succeeds and first session still valid → `CONFIRMED`
- `"logout_all_required"` → if POST logout-all fails to revoke other sessions → `CONFIRMED`
- `"security_change_revokes_old_sessions"` → if old sessions survive password change → `CONFIRMED`

Steps:
1. Login session-A
2. Login session-B (same user)
3. Check session-A still valid → if yes and policy is `single_session` → `CONFIRMED`
4. POST logout-all with session-B
5. Check session-A with revoked session → if still valid and policy requires revocation → `CONFIRMED`

`classify.py` input: `policy: str`, `session_a_survives_second_login: bool`,
  `session_a_survives_logout_all: bool`

- [ ] **Step 4.1: Write failing classify tests**:
  - `unknown` policy + session survives → `CANDIDATE` / `low`
  - `single_session` + session-A survives second login → `CONFIRMED` / `high`
  - `logout_all_required` + session-A survives logout-all → `CONFIRMED` / `high`
  - All sessions properly invalidated → `REJECTED` / `high`

- [ ] **Step 4.2: Write `classify.py`**:

```python
"""Stub 3.16 — Concurrent session weakness classification."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ConcurrentStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ConcurrentResult:
    status: ConcurrentStatus
    confidence: Literal["low", "medium", "high"]
    policy: str
    weakness_kind: str | None


def classify_concurrent(
    policy: str,
    session_a_survives_second_login: bool,
    session_a_survives_logout_all: bool,
) -> ConcurrentResult:
    if policy == "single_session" and session_a_survives_second_login:
        return ConcurrentResult(
            status=ConcurrentStatus.CONFIRMED, confidence="high",
            policy=policy, weakness_kind="old_session_not_revoked_on_new_login",
        )
    if policy == "logout_all_required" and session_a_survives_logout_all:
        return ConcurrentResult(
            status=ConcurrentStatus.CONFIRMED, confidence="high",
            policy=policy, weakness_kind="logout_all_did_not_revoke_all_sessions",
        )
    if policy == "unknown":
        if session_a_survives_logout_all:
            return ConcurrentResult(
                status=ConcurrentStatus.CANDIDATE, confidence="low",
                policy=policy, weakness_kind="session_survived_logout_all",
            )
        return ConcurrentResult(
            status=ConcurrentStatus.NOT_APPLICABLE, confidence="high",
            policy=policy, weakness_kind=None,
        )
    return ConcurrentResult(
        status=ConcurrentStatus.REJECTED, confidence="high",
        policy=policy, weakness_kind=None,
    )
```

- [ ] **Step 4.3: Write runner + tests**, **Step 4.4: Run + commit**

```bash
git add backend/apps/stubs/concurrent_session_weakness/
git commit -m "feat(stubs): 3.16 concurrent-session-weakness — session policy enforcement"
```

---

## Task 05: docker-compose wiring

```yaml
  session-cross-user-lab:
    build: ./fixtures/session-cross-user-lab
    image: earnmoney-session-cross-user-lab:dev
    ports:
      - "3007:3000"
    networks:
      - fixture-net
```

```bash
git add docker-compose.yml
git commit -m "feat(fixtures): wire session-cross-user-lab into docker-compose"
```

---

## After all tasks

Run `/code-review high` on Family D files, then open PR against Family C tip.
All four family PRs merged = Phase 3 complete.
