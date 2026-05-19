"""HTTP evidence collection for stub 1.3 frontend-framework.

Bounds runner cost on hostile targets: per-fetch byte caps prevent
unbounded body materialisation, per-target asset count caps prevent
fan-out abuse, and the same-origin / scheme filter keeps fetches
within the program's stated scope. See the spec for the full rule set.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/03-frontend-framework.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from .._shared.url import origin


DEFAULT_VERIFY = os.environ.get("FRONTEND_FRAMEWORK_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class FetcherConfig:
    max_linked_assets: int = 12
    max_asset_bytes: int = 262144
    max_body_bytes: int = 524288
    allow_external_asset_fetch: bool = False
    allow_source_map_fetch: bool = False

    def __post_init__(self) -> None:
        for name in ("max_linked_assets", "max_asset_bytes", "max_body_bytes"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0; got {getattr(self, name)}")


_DEFAULT_CONFIG = FetcherConfig()


def fetch_evidence(
    base_url: str, config: FetcherConfig | None = None
) -> dict:
    """Return one evidence bundle for the target's root + linked assets.

    Shape: {html_body, script_paths, asset_bodies, url}.
    On transport failure of the base URL, returns an empty-bundle shape
    so the runner can short-circuit cleanly without an exception."""
    config = config or _DEFAULT_CONFIG
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        verify=DEFAULT_VERIFY,
    ) as client:
        try:
            base_resp = client.get(base_url)
        except httpx.TransportError:
            return _empty_bundle(base_url)

        html_body = (base_resp.text or "")[: config.max_body_bytes]
        final_url = str(base_resp.url)
        link_srcs = _extract_srcs(html_body)
        script_paths = [_to_path(src) for src in link_srcs]
        asset_bodies = _fetch_assets(
            client, final_url, link_srcs, config
        )
        return {
            "html_body": html_body,
            "script_paths": script_paths,
            "asset_bodies": asset_bodies,
            "url": final_url,
        }


def _empty_bundle(url: str) -> dict:
    return {
        "html_body": "",
        "script_paths": [],
        "asset_bodies": {},
        "url": url,
    }


def _extract_srcs(html: str) -> list[str]:
    """Return raw src/href strings for asset-bearing tags — script[src]
    plus <link rel=stylesheet|modulepreload|preload(as=script)>.

    Returns originals (not resolved) so the fetcher can apply same-
    origin filtering on the real source before resolution overrides it."""
    soup = BeautifulSoup(html, "html.parser")
    srcs: list[str] = []
    for tag in soup.find_all("script", src=True):
        srcs.append(tag["src"])
    for tag in soup.find_all("link"):
        href = tag.get("href")
        if not href:
            continue
        if _link_is_asset(tag.get("rel") or [], tag.get("as")):
            srcs.append(href)
    return srcs


def _link_is_asset(rel: list[str], as_attr: str | None) -> bool:
    return (
        "stylesheet" in rel
        or "modulepreload" in rel
        or ("preload" in rel and as_attr == "script")
    )


def _to_path(src: str) -> str:
    if "://" in src:
        return urlsplit(src).path
    return src


def _fetch_assets(
    client: httpx.Client,
    base_url: str,
    srcs: list[str],
    config: FetcherConfig,
) -> dict[str, str]:
    bodies: dict[str, str] = {}
    base_origin = origin(base_url)
    for src in srcs:
        if len(bodies) >= config.max_linked_assets:
            break
        if not config.allow_source_map_fetch and src.endswith(".map"):
            continue
        asset_url = urljoin(base_url, src)
        # urljoin handles relative paths, absolute URLs, AND protocol-
        # relative `//cdn/x.js` correctly; the scheme check catches
        # absolute non-http(s) like `ftp://...` and pseudo-schemes like
        # `javascript:` that survived urljoin unchanged.
        if not asset_url.startswith(("http://", "https://")):
            continue
        if (
            not config.allow_external_asset_fetch
            and origin(asset_url) != base_origin
        ):
            continue
        body = _try_fetch(client, asset_url, config.max_asset_bytes)
        if body is None:
            continue
        bodies[_basename(asset_url)] = body
    return bodies


def _try_fetch(
    client: httpx.Client, url: str, max_bytes: int
) -> str | None:
    try:
        resp = client.get(url)
    except httpx.TransportError:
        return None
    return (resp.text or "")[:max_bytes]


def _basename(url: str) -> str:
    return urlsplit(url).path.rsplit("/", 1)[-1]
