"""Deterministic content extractors for stub 1.15.

Per spec §4 "Extract deterministic signatures from bundle content":
this module covers the URL-side and body-shape extractors —
filename, extension, canonical build hints, hash-in-filename, the
minified marker heuristic, and the //# sourceMappingURL=
reference. Framework/API/env/secret extractors land in later slices.

Every function is pure (str → str/bool/list/None) so the runner can
fan them out per bundle without orchestration cost.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlsplit


Extension = Literal["js", "mjs", "cjs", "jsx", "none", "unknown"]

# Canonical build-hint vocabulary per spec. Order is the canonical
# emit order so signature comparison is idempotent across reruns.
_BUILD_HINTS: tuple[str, ...] = (
    "main", "runtime", "vendor", "chunk", "app", "polyfills",
)
_BUILD_HINT_TOKEN_BOUNDARY = r"(?:^|[.\-_~])"
_BUILD_HINT_TAIL_BOUNDARY = r"(?:$|[.\-_~])"

# Hash-like segment: 6+ alphanumeric chars with at least one digit,
# bounded by `.` or `-`. Matches `main.8f31a2.js`, `chunk-ABC123.js`,
# `app.aB3xY9z2.js`. Pure-word segments (`vendor.bundle`) and short
# (<6) version tags (`app.v1`) are rejected.
_HASH_SEGMENT_RE = re.compile(
    r"[.\-]([A-Za-z0-9]{6,})[.\-]"
)
_HASH_PLACEHOLDER = "[hash]"

# Matches both spec JS forms — modern `//# sourceMappingURL=value`
# and legacy `//@ sourceMappingURL=value`. CSS comment form is
# deliberately excluded; this stub fetches JS bundles only.
_JS_SOURCE_MAP_RE = re.compile(
    r"^[ \t]*//[#@][ \t]*sourceMappingURL=[ \t]*(.+?)[ \t]*$",
    re.MULTILINE,
)

# Minified-marker thresholds. Tuned for the common minifier output
# (terser, esbuild, webpack production): single line of 1k+ chars,
# OR multiple lines whose average length is well past readable.
_MINIFIED_MIN_BYTES = 500
_MINIFIED_AVG_LINE_LEN_THRESHOLD = 250


def extract_filename(url: str) -> str | None:
    path = urlsplit(url).path
    if not path or path.endswith("/"):
        return None
    tail = path.rsplit("/", 1)[-1]
    return tail or None


def extract_extension(url: str) -> Extension:
    name = extract_filename(url)
    if name is None or "." not in name:
        return "none"
    ext = name.rsplit(".", 1)[-1].lower()
    if ext in ("js", "mjs", "cjs", "jsx"):
        return ext  # type: ignore[return-value]
    return "unknown"


def extract_build_hints(filename: str) -> list[str]:
    found: list[str] = []
    for hint in _BUILD_HINTS:
        pattern = (
            _BUILD_HINT_TOKEN_BOUNDARY
            + re.escape(hint)
            + _BUILD_HINT_TAIL_BOUNDARY
        )
        if re.search(pattern, filename):
            found.append(hint)
    return found


def extract_hash_in_filename(filename: str) -> bool:
    if _HASH_PLACEHOLDER in filename:
        return True
    for match in _HASH_SEGMENT_RE.findall(filename):
        if any(c.isdigit() for c in match):
            return True
    return False


def extract_source_map_url(body: str) -> str | None:
    if not body:
        return None
    matches = _JS_SOURCE_MAP_RE.findall(body)
    if not matches:
        return None
    return matches[-1].strip()


def extract_minified_marker(body: str) -> bool:
    """Heuristic — minified bundles have far fewer newlines per byte
    than readable source. Below `_MINIFIED_MIN_BYTES` the signal is
    too noisy (utility scripts, snippets), so we abstain → False."""
    if len(body) < _MINIFIED_MIN_BYTES:
        return False
    lines = body.splitlines() or [body]
    avg_line_len = len(body) / len(lines)
    return avg_line_len >= _MINIFIED_AVG_LINE_LEN_THRESHOLD
