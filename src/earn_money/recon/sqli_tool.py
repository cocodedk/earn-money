"""SQLi probe — error-based and boolean-based detection via GET parameters.

GET-only. Never replays POST bodies. Reads discovered URLs (from katana
JSONL) and tests each URL parameter for injection indicators. Time-based
payloads are off by default; roe.md must set sqli_time_based: true.
"""

from __future__ import annotations

import json
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from earn_money.recon.signals import Signal
from earn_money.triage import hashing

# DB error fragments that reliably indicate error-based SQLi.
ERROR_PATTERNS: tuple[str, ...] = (
    "you have an error in your sql syntax",
    "warning: mysql",
    "mysql_num_rows",
    "ora-00933",
    "ora-01756",
    "pg_query",
    "invalid input syntax for",
    "sqlite3",
    "microsoft ole db provider for sql server",
    "unclosed quotation mark",
    "quoted string not properly terminated",
)

_ERR_PAYLOAD = "'"
_BOOL_TRUE = "' OR '1'='1"
_BOOL_FALSE = "' OR '1'='2"
_BOOL_RATIO_THRESHOLD = 0.05  # 5% content-length difference triggers boolean flag


def probe_url(
    url: str,
    *,
    client: httpx.Client,
    run_id: str,
    observed_at: str,
    request_interval: float = 0.0,
) -> list[Signal]:
    """Test each GET parameter in `url` for error-based or boolean SQLi."""
    params = parse_qs(urlparse(url).query, keep_blank_values=True)
    if not params:
        return []
    signals: list[Signal] = []
    for param in params:
        result = _probe_param(url, param, client=client, request_interval=request_interval)
        if result is None:
            continue
        kind, evidence = result
        signals.append(
            _make_signal(url, param, kind, evidence, run_id=run_id, observed_at=observed_at)
        )
    return signals


def _inject(url: str, param: str, value: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[param] = [value]
    return urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in params.items()})))


def _probe_param(
    url: str, param: str, *, client: httpx.Client, request_interval: float = 0.0,
) -> tuple[str, str] | None:
    """Return (kind, evidence) if the param appears injectable, else None."""
    try:
        err_resp = client.get(_inject(url, param, _ERR_PAYLOAD))
        if request_interval:
            time.sleep(request_interval)
        body_lower = err_resp.text.lower()
        for pattern in ERROR_PATTERNS:
            if pattern in body_lower:
                return "error_based", f"matched:{pattern!r}"

        true_resp = client.get(_inject(url, param, _BOOL_TRUE))
        if request_interval:
            time.sleep(request_interval)
        false_resp = client.get(_inject(url, param, _BOOL_FALSE))
        if request_interval:
            time.sleep(request_interval)
        tl, fl = len(true_resp.text), len(false_resp.text)
        if tl > 0 and fl > 0:
            ratio = abs(tl - fl) / max(tl, fl)
            if ratio > _BOOL_RATIO_THRESHOLD:
                return "boolean_based", f"true_len={tl} false_len={fl} ratio={ratio:.2f}"
    except httpx.HTTPError:
        return None
    return None


def _make_signal(
    url: str, param: str, kind: str, evidence: str,
    *, run_id: str, observed_at: str,
) -> Signal:
    asset = hashing.normalize_asset(url)
    target = hashing.normalize_target(url)
    signature = f"sqli|{kind}|{param}|{target[:20]}"
    payload = json.dumps(
        {"url": url, "param": param, "kind": kind, "evidence": evidence, "severity": "high"},
        sort_keys=True,
    )
    return Signal(
        run_id=run_id, tool="sqli-probe", signal_type="sqli_candidate",
        asset=asset, target=target, signature=signature,
        payload=payload, observed_at=observed_at,
    )
