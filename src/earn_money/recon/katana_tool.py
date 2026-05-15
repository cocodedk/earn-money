"""Subprocess wrapper around ProjectDiscovery `katana`.

Katana follows links from seed URLs and reports each discovered
endpoint as a JSONL line. We parse the lines into `DiscoveredUrl`
records — the runner re-checks each URL against the program's live
scope before persisting anything.

No script-rendered crawl (`-jc`) and no POST follow: bounty programs
typically don't authorize state mutation from automated crawlers,
and -jc requires a headless Chrome the VPS doesn't run.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse


class KatanaUnavailable(Exception):
    """Raised when the katana binary is missing on PATH."""


@dataclass(frozen=True)
class DiscoveredUrl:
    url: str
    status_code: int | None
    content_type: str | None
    method: str


def build_command(
    targets_file: str,
    *,
    rate_limit: int,
    depth: int = 2,
    concurrency: int = 10,
    crawl_scope: Sequence[str] = (),
) -> list[str]:
    """Build the `katana` argv for crawling a list of seed URLs.

    `targets_file` is a newline-delimited file of seed URLs. `rate_limit`
    is requests-per-second. `depth` caps crawl recursion. `concurrency`
    is parallel workers. `crawl_scope` provides explicit `-cs` hosts so
    katana never issues requests to OOS hosts before the post-filter runs;
    values should be already-validated live hosts (from `http_services`),
    not raw `scope.md` patterns.
    """
    if rate_limit <= 0:
        raise ValueError(f"rate_limit must be positive, got {rate_limit}")
    if depth <= 0:
        raise ValueError(f"depth must be positive, got {depth}")
    if concurrency <= 0:
        raise ValueError(f"concurrency must be positive, got {concurrency}")
    cmd = [
        "katana",
        "-list", targets_file,
        "-jsonl",
        "-silent",
        "-no-color",
        "-rate-limit", str(rate_limit),
        "-depth", str(depth),
        "-concurrency", str(concurrency),
    ]
    for host in crawl_scope:
        # Katana -cs is a URL regex; anchor with scheme so bare hostname patterns don't match.
        pattern = r"^https?://" + re.escape(host).replace(r"\*", ".*") + r"(?::\d+)?(?:/.*)?$"
        cmd.extend(["-cs", pattern])
    return cmd


def parse_jsonl(raw: str) -> list[DiscoveredUrl]:
    """Parse katana's JSONL output. Silently skips malformed lines."""
    out: list[DiscoveredUrl] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        url = _extract_url(data)
        if url is None:
            continue
        out.append(DiscoveredUrl(
            url=url,
            status_code=_int_or_none(_response(data).get("status_code")),
            content_type=_str_or_none(_response(data).get("content_type")),
            method=_str_or_none(_request(data).get("method")) or "GET",
        ))
    return out


def _request(data: dict[str, object]) -> dict[str, object]:
    req = data.get("request")
    return req if isinstance(req, dict) else {}


def _response(data: dict[str, object]) -> dict[str, object]:
    resp = data.get("response")
    return resp if isinstance(resp, dict) else {}


def _extract_url(data: dict[str, object]) -> str | None:
    """Endpoint URL — first try request.endpoint (katana v1 shape),
    fall back to top-level 'output' field used by older versions."""
    req = _request(data)
    endpoint = req.get("endpoint")
    if isinstance(endpoint, str) and endpoint:
        return endpoint
    legacy = data.get("output") or data.get("url")
    if isinstance(legacy, str) and legacy:
        return legacy
    return None


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def filter_in_scope(
    urls: Sequence[DiscoveredUrl],
    *,
    in_scope_host: Callable[[str], bool],
) -> tuple[list[DiscoveredUrl], int]:
    """Return (in_scope_urls, oos_drop_count) for live-scope re-check."""
    keep: list[DiscoveredUrl] = []
    drops = 0
    for u in urls:
        host = _host_of(u.url)
        if host and in_scope_host(host):
            keep.append(u)
        else:
            drops += 1
    return keep, drops


def _host_of(url: str) -> str:
    return urlparse(url).hostname or ""
