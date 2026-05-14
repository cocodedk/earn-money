"""Front-end JS bundle / sourcemap analyzer.

For each target URL: fetch HTML, extract `<script src=>` references,
filter to in-scope hosts, download each script, look for a
`//# sourceMappingURL=...` comment, fetch the map if present, and
run `secret_patterns.find_secrets` over both bodies.

The HTTP client is injected so the runner can wire its own
timeout/UA/cookie policy and tests can use `httpx.MockTransport`.
Scope is enforced via an `in_scope` callback the runner passes in —
this module never trusts a host without that check.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from earn_money.recon.secret_patterns import (
    SecretMatch,
    find_secrets,
    redact,
)
from earn_money.recon.signals import Signal

InScope = Callable[[str], bool]

_SCRIPT_SRC = re.compile(
    r'<script[^>]+src=["\']([^"\'>\s]+)["\']',
    re.IGNORECASE,
)
_SOURCEMAP_COMMENT = re.compile(
    r"//[#@]\s*sourceMappingURL=([^\s'\"]+)",
)


@dataclass(frozen=True)
class ScanResult:
    signals: tuple[Signal, ...]
    scripts_fetched: int
    sourcemaps_fetched: int


def extract_script_urls(html: str, base_url: str) -> list[str]:
    """Return absolute `<script src=>` URLs found in `html`.

    Relative paths resolve against `base_url`. Inline scripts (no src)
    are ignored; this scanner only follows external bundle references.
    """
    return [
        urljoin(base_url, m.group(1))
        for m in _SCRIPT_SRC.finditer(html)
    ]


def find_sourcemap_url(js_source: str, js_url: str) -> str | None:
    """Return the absolute URL of the sourcemap comment if present."""
    m = _SOURCEMAP_COMMENT.search(js_source)
    if not m:
        return None
    resolved: str = urljoin(js_url, m.group(1))
    return resolved


def _host_of(url: str) -> str:
    return urlparse(url).hostname or ""


def _signal_for_secret(
    match: SecretMatch,
    *,
    source_url: str,
    run_id: str,
    observed_at: str,
) -> Signal:
    host = _host_of(source_url)
    payload = json.dumps(
        {
            "pattern": match.pattern_name,
            "severity": match.severity,
            "redacted_value": redact(match.value),
            "source_url": source_url,
            "offset": match.start,
        },
        sort_keys=True,
    )
    return Signal(
        run_id=run_id,
        tool="sourcemap-scan",
        signal_type="leaked_secret",
        asset=host,
        target=source_url,
        signature=f"sourcemap|{match.pattern_name}|{redact(match.value)}",
        payload=payload,
        observed_at=observed_at,
    )


def _signal_for_exposed_map(
    map_url: str, *, run_id: str, observed_at: str,
) -> Signal:
    host = _host_of(map_url)
    return Signal(
        run_id=run_id,
        tool="sourcemap-scan",
        signal_type="exposed_sourcemap",
        asset=host,
        target=map_url,
        signature=f"sourcemap|exposed|{map_url}",
        payload=json.dumps({"severity": "info"}, sort_keys=True),
        observed_at=observed_at,
    )


def _safe_get(client: httpx.Client, url: str) -> httpx.Response | None:
    try:
        resp = client.get(url)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    return resp


def scan_target(
    base_url: str,
    *,
    client: httpx.Client,
    in_scope: InScope,
    run_id: str,
    observed_at: str,
) -> ScanResult:
    """Fetch HTML at `base_url`, follow same-scope script srcs, hunt secrets."""
    html_resp = _safe_get(client, base_url)
    if html_resp is None:
        return ScanResult(signals=(), scripts_fetched=0, sourcemaps_fetched=0)

    script_urls = [
        u for u in extract_script_urls(html_resp.text, base_url)
        if in_scope(_host_of(u))
    ]

    out: list[Signal] = []
    scripts_fetched = 0
    maps_fetched = 0
    for js_url in script_urls:
        js_resp = _safe_get(client, js_url)
        if js_resp is None:
            continue
        scripts_fetched += 1
        for m in find_secrets(js_resp.text):
            out.append(
                _signal_for_secret(
                    m, source_url=js_url,
                    run_id=run_id, observed_at=observed_at,
                )
            )
        map_url = find_sourcemap_url(js_resp.text, js_url)
        if map_url is None or not in_scope(_host_of(map_url)):
            continue
        map_resp = _safe_get(client, map_url)
        if map_resp is None:
            continue
        maps_fetched += 1
        out.append(
            _signal_for_exposed_map(
                map_url, run_id=run_id, observed_at=observed_at,
            )
        )
        for m in find_secrets(map_resp.text):
            out.append(
                _signal_for_secret(
                    m, source_url=map_url,
                    run_id=run_id, observed_at=observed_at,
                )
            )

    return ScanResult(
        signals=tuple(out),
        scripts_fetched=scripts_fetched,
        sourcemaps_fetched=maps_fetched,
    )
