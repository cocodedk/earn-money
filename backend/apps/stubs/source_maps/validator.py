"""Source Map v3 validator + metadata extractor (stub 1.14 slice 4).

Parses a fetched ``.map`` response body and emits the deterministic
metadata the runner persists per spec §"Extracted deterministic
attributes". Never decodes ``sourcesContent`` — counts and flags
only — so we don't accidentally store full source files.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/14-source-maps.md
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .path_categories import categorise_sources, find_internal_indicators


_PATH_SAMPLE_CAP = 10


@dataclass(frozen=True)
class SourceMapMetadata:
    """Deterministic shape persisted on the SourceMapSignature row.

    ``version`` is the raw ``version`` field from the JSON; spec lists
    ``3`` as the v3 marker but doesn't pin it strictly — bundlers
    sometimes emit ``"3"`` or other values. The runner stores
    whatever was there so audits keep the original value.
    """
    version: int | None
    sources_count: int
    sources_content_count: int
    has_sources_content: bool
    has_source_root: bool
    has_sections: bool
    source_path_samples: tuple[str, ...]
    source_path_categories: tuple[str, ...]
    internal_path_indicators: tuple[str, ...]


def parse_source_map(body: str) -> SourceMapMetadata | None:
    """Return populated metadata when ``body`` parses as a Source Map
    v3 object, or ``None`` when it doesn't.

    The shape check follows spec §"Source map fetch": top-level
    object, must have ``version`` AND at least one of ``sources``,
    ``sections``, or ``mappings``. Anything else (HTML 404 body,
    JSON array, missing keys) returns ``None``.
    """
    if not body:
        return None
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if "version" not in data:
        return None
    if not any(key in data for key in ("sources", "sections", "mappings")):
        return None
    return _extract_metadata(data)


def _extract_metadata(data: dict) -> SourceMapMetadata:
    sources = _string_entries(data.get("sources"))
    sources_content = data.get("sourcesContent")
    sources_content_count = (
        len(sources_content) if isinstance(sources_content, list) else 0
    )
    categories, indicators = _walk_paths(sources)
    return SourceMapMetadata(
        version=_as_int(data.get("version")),
        sources_count=len(sources),
        sources_content_count=sources_content_count,
        has_sources_content=bool(sources_content_count),
        has_source_root=isinstance(data.get("sourceRoot"), str),
        has_sections=isinstance(data.get("sections"), list),
        source_path_samples=tuple(sources[:_PATH_SAMPLE_CAP]),
        source_path_categories=tuple(categories),
        internal_path_indicators=tuple(indicators),
    )


def _string_entries(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, str)]


def _walk_paths(sources: list[str]) -> tuple[list[str], list[str]]:
    """Bridge to the deterministic per-path classifiers in
    ``path_categories``. Returns ``(categories, indicators)`` as
    sorted, deduped lists in their respective predefined orders."""
    categories = categorise_sources(sources)
    indicators = find_internal_indicators(sources)
    return categories, indicators


def _as_int(value) -> int | None:
    """`version` is normally `3` but bundlers may emit other shapes."""
    if isinstance(value, bool):
        # bool is a subclass of int in Python — explicit reject.
        return None
    if isinstance(value, int):
        return value
    return None
