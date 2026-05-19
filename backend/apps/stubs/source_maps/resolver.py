"""Map URL resolver for stub 1.14 source-maps (slice 3).

Resolves the raw ``sourceMappingURL`` value pulled by
``parser.extract_source_mapping_url`` into an absolute URL the
fetcher can probe — or classifies it as inline/cross-origin/
invalid per spec §"Source map reference detection".

The resolver never makes network calls and never decodes inline
``data:`` payloads. The runner uses the result kind to decide
whether to fetch (`ok`), emit a candidate finding without
fetching (`inline_data_url`), or skip the candidate
(`cross_origin` / `invalid`) with a diagnostic.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin, urlsplit

from .._shared.url import origin


ResolvedKind = Literal["ok", "inline_data_url", "cross_origin", "invalid"]


@dataclass(frozen=True)
class ResolvedMapUrl:
    """Result of resolving a raw ``sourceMappingURL`` value.

    ``absolute_url`` is populated only when ``kind="ok"``; for
    every rejection kind the runner gets ``None`` so it can't
    accidentally fetch a denied URL.
    """
    kind: ResolvedKind
    absolute_url: str | None


def resolve_map_url(raw: str, asset_url: str) -> ResolvedMapUrl:
    """Resolve ``raw`` against ``asset_url`` and classify the result.

    Accepted shapes (kind="ok"): relative, root-relative, and
    absolute same-origin URLs over http/https. Query strings and
    fragments are preserved on accepted URLs.

    Rejected shapes:
    * ``data:`` → ``kind="inline_data_url"`` so the runner can emit
      a spec-compliant candidate without decoding the body.
    * Cross-origin http(s) (different scheme, host, or port) →
      ``kind="cross_origin"``.
    * Anything else (``javascript:``, ``file:``, ``ftp:``,
      ``blob:``, ``mailto:``, empty, malformed) → ``kind="invalid"``.
    """
    stripped = (raw or "").strip()
    if not stripped:
        return ResolvedMapUrl(kind="invalid", absolute_url=None)
    if _is_inline_data_url(stripped):
        return ResolvedMapUrl(kind="inline_data_url", absolute_url=None)

    absolute = urljoin(asset_url, stripped)
    scheme = urlsplit(absolute).scheme
    if scheme not in {"http", "https"}:
        return ResolvedMapUrl(kind="invalid", absolute_url=None)

    if origin(absolute) != origin(asset_url):
        return ResolvedMapUrl(kind="cross_origin", absolute_url=None)
    return ResolvedMapUrl(kind="ok", absolute_url=absolute)


def _is_inline_data_url(value: str) -> bool:
    return value.lower().startswith("data:")
