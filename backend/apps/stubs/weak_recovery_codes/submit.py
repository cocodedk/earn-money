"""Recovery-code helpers for stub 2.12.

`generate_recovery_codes()` posts to the candidate endpoints
typical apps expose for one-shot recovery-code issuance.
`extract_codes_from()` parses the response body for the codes,
handling the common shapes:

- `{"codes": ["...", "..."]}`
- `{"recovery_codes": [...]}` / `{"recoveryCodes": [...]}`
- `{"backup_codes": [...]}`
- top-level array of strings
- nested `{"data": {"codes": [...]}}`
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from httpx import Client


_DEFAULT_TIMEOUT = 10.0
_ENDPOINTS: tuple[str, ...] = (
    "/mfa/recovery-codes/generate",
    "/api/mfa/recovery-codes",
    "/account/mfa/recovery-codes",
    "/security/recovery-codes",
)
# Keys whose value is the codes array. Order matters — most
# specific first so a target carrying both `codes` and a vendor
# wrapper hits the canonical key.
_CODE_KEYS: tuple[str, ...] = (
    "codes", "recovery_codes", "recoveryCodes",
    "backup_codes", "backupCodes",
)


def generate_recovery_codes(
    *, base_url: str, bearer_token: str,
) -> httpx.Response | None:
    """POST to candidate recovery-code endpoints. Return the first
    non-404/405 response. None on transport failure for all paths."""
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "content-type": "application/json",
    }
    last: httpx.Response | None = None
    for path in _ENDPOINTS:
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


def extract_codes_from(response: httpx.Response) -> list[str]:
    """Pull recovery codes out of the response body. Returns an
    empty list if the body doesn't parse as JSON or carries no
    recognised array."""
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        return []
    if isinstance(body, list):
        return [str(x) for x in body if isinstance(x, str)]
    if not isinstance(body, dict):
        return []
    return _find_codes(body)


def _find_codes(payload: Any, depth: int = 0) -> list[str]:
    """Bounded recursive walk (depth ≤ 3) over dict values looking
    for the first list of strings at any `_CODE_KEYS` field."""
    if depth > 3 or not isinstance(payload, dict):
        return []
    for key in _CODE_KEYS:
        value = payload.get(key)
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            return value
    for v in payload.values():
        nested = _find_codes(v, depth + 1)
        if nested:
            return nested
    return []
