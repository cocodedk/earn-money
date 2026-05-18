"""HTML + linked-asset fetcher for stub 1.3 frontend-framework.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/03-frontend-framework.md
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup


DEFAULT_VERIFY = os.environ.get("FRONTEND_FRAMEWORK_VERIFY", "1") != "0"
DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class FetcherConfig:
    max_linked_assets: int = 12
    max_asset_bytes: int = 262144
    max_body_bytes: int = 524288
    allow_external_asset_fetch: bool = False
    allow_source_map_fetch: bool = False


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

        html_body = _truncate(base_resp.text or "", config.max_body_bytes)
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


def _truncate(text: str, limit: int) -> str:
    return text[:limit] if len(text) > limit else text


def _extract_srcs(html: str) -> list[str]:
    """Return the raw src/href strings from script + asset link tags.

    Returns the original strings (possibly absolute URLs, possibly
    relative paths) so the fetcher can do same-origin filtering on the
    real source before resolution overrides it."""
    soup = BeautifulSoup(html, "html.parser")
    srcs: list[str] = []
    for tag in soup.find_all("script", src=True):
        srcs.append(tag["src"])
    for tag in soup.find_all("link"):
        rel = tag.get("rel") or []
        href = tag.get("href")
        if not href:
            continue
        if _link_is_asset(rel, tag.get("as")):
            srcs.append(href)
    return srcs


def _link_is_asset(rel: list[str], as_attr: str | None) -> bool:
    if "stylesheet" in rel:
        return True
    if "modulepreload" in rel:
        return True
    if "preload" in rel and as_attr == "script":
        return True
    return False


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
    base_origin = _origin(base_url)
    for src in srcs:
        if len(bodies) >= config.max_linked_assets:
            break
        if not config.allow_source_map_fetch and src.endswith(".map"):
            continue
        asset_url = _resolve(base_url, src)
        if not asset_url.startswith(("http://", "https://")):
            continue
        if (
            not config.allow_external_asset_fetch
            and _origin(asset_url) != base_origin
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
    return _truncate(resp.text or "", max_bytes)


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _resolve(base_url: str, path_or_url: str) -> str:
    if "://" in path_or_url:
        return path_or_url
    return f"{_origin(base_url)}{path_or_url}"


def _basename(url: str) -> str:
    return urlsplit(url).path.rsplit("/", 1)[-1]
