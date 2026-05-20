"""GitHub ownership-check helpers for takeover triage.

Extracted from verify_takeover_cli.py — provides _github_user_lookup()
and _extract_github_name(). Kept as private helpers; the CLI imports
them by name so monkeypatching in tests still works.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


def _github_user_lookup(name: str) -> tuple[int, dict[str, Any]]:
    """Return (status, body). status=0 on network failure (indeterminate).

    Reads ``GITHUB_TOKEN`` from the environment when present and sends it
    as a Bearer token — the unauthenticated quota is 60 requests/hour
    per IP, low enough to hit on a busy day. 403 with the rate-limit
    headers set surfaces as status 429 + an error body so the caller
    can distinguish "rate-limited" from "actually-claimed-but-forbidden".
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.get(
            f"https://api.github.com/users/{name}",
            timeout=10.0,
            headers=headers,
        )
    except httpx.HTTPError:
        return 0, {}
    if r.status_code == 200:
        try:
            return 200, r.json()
        except ValueError:
            return 200, {}
    if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
        return 429, {
            "rate_limit_reset": r.headers.get("X-RateLimit-Reset", ""),
            "error": "GitHub API rate limit exhausted; set GITHUB_TOKEN to raise it.",
        }
    return r.status_code, {}


def _extract_github_name(payload: str) -> str | None:
    """Pull the GitHub user/org name out of payload.extracted (e.g.
    'hacker0x01.github.io' → 'hacker0x01'). Returns None on parse failure."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    host = str(parsed.get("extracted", ""))
    if not host.endswith(".github.io"):
        return None
    return host[: -len(".github.io")]
