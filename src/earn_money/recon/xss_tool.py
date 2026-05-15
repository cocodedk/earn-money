"""XSS probe — reflected-XSS detection via GET parameter injection.

Injects a non-executing marker string into each URL parameter and checks
whether it is reflected verbatim in the response body. GET-only.
"""

from __future__ import annotations

import json
import uuid
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from earn_money.recon.signals import Signal
from earn_money.triage import hashing

_MARKER_PREFIX = "xsspwn"


def _marker() -> str:
    """Generate a per-run unique marker (no special HTML chars — safe to inject)."""
    return f"{_MARKER_PREFIX}{uuid.uuid4().hex[:8]}"


def probe_url(
    url: str,
    *,
    client: httpx.Client,
    run_id: str,
    observed_at: str,
) -> list[Signal]:
    """Test each GET parameter for reflected XSS by checking marker reflection."""
    params = parse_qs(urlparse(url).query, keep_blank_values=True)
    if not params:
        return []
    signals: list[Signal] = []
    for param in params:
        marker = _marker()
        result = _probe_param(url, param, marker, client=client)
        if not result:
            continue
        signals.append(_make_signal(url, param, marker, run_id=run_id, observed_at=observed_at))
    return signals


def _inject(url: str, param: str, value: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[param] = [value]
    return urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in params.items()})))


def _probe_param(url: str, param: str, marker: str, *, client: httpx.Client) -> bool:
    """Return True if `marker` appears in the response body."""
    try:
        resp = client.get(_inject(url, param, marker))
        return marker in resp.text
    except httpx.HTTPError:
        return False


def _make_signal(
    url: str, param: str, marker: str,
    *, run_id: str, observed_at: str,
) -> Signal:
    asset = hashing.normalize_asset(url)
    target = hashing.normalize_target(url)
    normalized = hashing.normalize_target(url)
    signature = f"xss|reflected|{param}|{normalized[:20]}"
    payload = json.dumps(
        {"url": url, "param": param, "marker": marker, "severity": "medium"},
        sort_keys=True,
    )
    return Signal(
        run_id=run_id, tool="xss-probe", signal_type="xss_candidate",
        asset=asset, target=target, signature=signature,
        payload=payload, observed_at=observed_at,
    )
