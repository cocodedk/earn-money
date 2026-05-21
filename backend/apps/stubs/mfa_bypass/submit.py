"""MFA-bypass submit helpers for stub 2.10.

`enroll_mfa()` flips the canary's MFA flag (POSTs to the candidate
enrollment paths). `post_sensitive_action()` is the load-bearing
probe: it hits the sensitive-action candidate paths with ONLY a
session bearer — no MFA step-up header — so a 2xx response means
the target lets the action through despite MFA enrollment.

Codex P1.2: the sensitive-action path list defaults to the
canonical fixture-safe routes only. Destructive endpoints
(`/admin/promote`, `/account/delete`, etc.) are NEVER probed
unless the operator opts in via `FIXTURE_SENSITIVE_ACTION_PATHS`
(comma-separated) — the synthetic canary account makes the
fixture-default safe; real H1 targets need explicit per-program
opt-in.
"""
from __future__ import annotations

import os

import httpx
from httpx import Client


_DEFAULT_TIMEOUT = 10.0
_ENROLL_PATHS: tuple[str, ...] = (
    "/mfa/enroll",
    "/api/mfa/enroll",
    "/account/mfa/enable",
    "/api/account/mfa",
    "/security/mfa/enroll",
)
# Fixture-safe defaults only. `/sensitive-action` is the
# reset-canary endpoint name; operators with a real target that
# exposes a different name set FIXTURE_SENSITIVE_ACTION_PATHS.
_DEFAULT_SENSITIVE_PATHS: tuple[str, ...] = (
    "/sensitive-action",
    "/api/sensitive-action",
)


def _sensitive_paths() -> tuple[str, ...]:
    raw = os.environ.get("FIXTURE_SENSITIVE_ACTION_PATHS", "").strip()
    if not raw:
        return _DEFAULT_SENSITIVE_PATHS
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def _post_with_bearer(
    *, base_url: str, paths: tuple[str, ...], bearer_token: str,
) -> httpx.Response | None:
    """Try each candidate path with `Authorization: Bearer <token>`
    and an empty JSON body. Return the first non-404/405 response.
    None on transport failure for every path."""
    last: httpx.Response | None = None
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "content-type": "application/json",
    }
    for path in paths:
        url = base_url.rstrip("/") + path
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
            ) as client:
                resp = client.post(url, headers=headers, json={})
        except httpx.RequestError:
            continue
        last = resp
        if resp.status_code in (404, 405):
            continue
        return resp
    return last


def enroll_mfa(
    *, base_url: str, bearer_token: str,
) -> httpx.Response | None:
    """POST to a candidate MFA-enrollment path. Return the first
    non-404/405 response."""
    return _post_with_bearer(
        base_url=base_url, paths=_ENROLL_PATHS,
        bearer_token=bearer_token,
    )


_ME_PATHS: tuple[str, ...] = (
    "/me", "/api/me", "/account", "/api/account",
    "/profile", "/api/profile",
)


def verify_mfa_enrolled(
    *, base_url: str, bearer_token: str,
) -> bool | None:
    """GET candidate `/me`-style paths and look for a truthy
    `mfaEnabled` / `mfa_enabled` field in the body. Returns:
    - True  → MFA confirmed enrolled
    - False → endpoint responded but mfa flag false / missing
    - None  → no usable response (404 everywhere, transport error)
    Used as a precondition for stub 2.10 (codex P2.1)."""
    headers = {"authorization": f"Bearer {bearer_token}"}
    for path in _ME_PATHS:
        url = base_url.rstrip("/") + path
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
            ) as client:
                resp = client.get(url, headers=headers)
        except httpx.RequestError:
            continue
        if resp.status_code in (404, 405):
            continue
        if not (200 <= resp.status_code < 300):
            return False
        try:
            body = resp.json()
        except (ValueError, TypeError):
            return False
        if not isinstance(body, dict):
            return False
        for key in ("mfaEnabled", "mfa_enabled", "isMfaEnabled"):
            if body.get(key) is True:
                return True
        return False
    return None


def post_sensitive_action(
    *, base_url: str, bearer_token: str,
) -> httpx.Response | None:
    """POST to a candidate sensitive-action path with no MFA
    step-up header. Return the first non-404/405 response."""
    return _post_with_bearer(
        base_url=base_url, paths=_sensitive_paths(),
        bearer_token=bearer_token,
    )
