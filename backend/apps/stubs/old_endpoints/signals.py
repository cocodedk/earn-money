"""Deterministic signal detectors for stub 1.9.

Three signal families per spec §Detection logic step 5:
- `header_deprecation_evidence`: scans response headers for RFC 8594
  Deprecation/Sunset, RFC 7234 Warning code 299, and Link with
  rel=deprecation|sunset.
- `body_has_deprecation_marker`: case-insensitive substring scan for
  the explicit deprecation/sunset phrases the spec calls out.
- `path_has_stale_token_segment`: segment-not-substring match against
  the seeded stale-token list. Returns the FIRST matching token.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/09-old-endpoints.md
"""
from __future__ import annotations

import re

from .._shared.body_match import contains_any
from .candidates import STALE_TOKENS


# RFC 7234 §5.5 warn-code 299 is "Miscellaneous Persistent Warning";
# vendors use it for deprecation messages. Lower codes (199 etc.) are
# transient and must not trigger deprecation evidence.
_WARNING_299_RE = re.compile(r"\b299\b")

# RFC 8288 §3.3 — `Link: <uri>; rel="<value>"`. Match `rel=` followed
# by an optional quote and the target relation. Anchored on `rel=`
# rather than full Link parsing because the spec only cares about
# deprecation|sunset and the structure is well-known.
_LINK_REL_RE = re.compile(r'rel\s*=\s*"?([\w.-]+)"?', re.IGNORECASE)


_BODY_MARKERS: tuple[str, ...] = (
    "deprecated",
    "deprecation",
    "legacy endpoint",
    "legacy api",
    "old endpoint",
    "sunset",
    "no longer maintained",
    "end of life",
    "end-of-life",
    "obsolete",
    "retired",
    "use /api/v2",
    "use /api/v3",
    "use the new api",
)


def header_deprecation_evidence(headers: dict[str, str]) -> list[str]:
    """Return a list of stable evidence keys for deprecation-indicating
    headers found in `headers`. Keys mirror the spec's stale_indicators
    vocabulary so they can be persisted into Finding.data without
    transformation."""
    lowered = {k.lower(): v for k, v in headers.items()}
    out: list[str] = []
    if "deprecation" in lowered:
        out.append("header:Deprecation")
    if "sunset" in lowered:
        out.append("header:Sunset")
    warning = lowered.get("warning", "")
    if warning and _WARNING_299_RE.search(warning):
        out.append("header:Warning:299")
    link = lowered.get("link", "")
    for match in _LINK_REL_RE.finditer(link):
        rel = match.group(1).lower()
        if rel in {"deprecation", "sunset"}:
            out.append(f"header:Link:rel={rel}")
    return out


def body_has_deprecation_marker(body: str) -> bool:
    """Case-insensitive scan for the deprecation phrases the spec
    enumerates under §Body indicators."""
    return contains_any(body, _BODY_MARKERS)


def path_has_stale_token_segment(path: str) -> str | None:
    """Return the FIRST stale token that appears as a path SEGMENT
    (between `/` delimiters), or None.

    Spec §Token matching rules: segments only — `v1` matches
    `/api/v1/users` but not `/assets/app.v1.js` (filename, not
    segment). The split-by-`/` form enforces this naturally."""
    if not path:
        return None
    segments = path.lower().split("/")
    for segment in segments:
        if segment in STALE_TOKENS:
            return segment
    return None
