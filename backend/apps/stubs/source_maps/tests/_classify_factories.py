"""Shared factories for the classify test suite (stub 1.14 slice 6).

Builds FetchOutcome / ResolvedMapUrl / SourceMapMetadata instances
with sensible defaults so each test in test_classify.py varies
only the field it cares about. Extracted from the test module to
respect the 200-line file cap.
"""
from __future__ import annotations

from ..fetcher import FetchOutcome
from ..resolver import ResolvedMapUrl
from ..validator import SourceMapMetadata


_BASE = "https://example.test"


def ok_asset(url: str = f"{_BASE}/a.js") -> FetchOutcome:
    return FetchOutcome(
        kind="ok", status=200, body="x", final_url=url,
        content_type="application/javascript",
    )


def ok_map(
    url: str = f"{_BASE}/a.js.map", body: str = "{}",
) -> FetchOutcome:
    return FetchOutcome(
        kind="ok", status=200, body=body, final_url=url,
        content_type="application/json",
    )


def metadata(
    *, has_sources_content: bool = False,
    internal_path_indicators: tuple[str, ...] = (),
) -> SourceMapMetadata:
    return SourceMapMetadata(
        version=3, sources_count=1, sources_content_count=0,
        has_sources_content=has_sources_content,
        has_source_root=False, has_sections=False,
        source_path_samples=("webpack://app/x.ts",),
        source_path_categories=("webpack",),
        internal_path_indicators=internal_path_indicators,
    )


def resolved_ok(url: str = f"{_BASE}/a.js.map") -> ResolvedMapUrl:
    return ResolvedMapUrl(kind="ok", absolute_url=url)
