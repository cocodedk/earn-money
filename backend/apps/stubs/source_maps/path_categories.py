"""Per-source path classifier for stub 1.14 (slice 4 helper).

Pure deterministic functions that map source-map ``sources`` entries
to the spec's category vocabulary and internal-path indicator set.
No AI. No fetching. Substring-only matching.

Spec §"Extracted deterministic attributes": categories vocabulary
is closed at twelve values; the indicator list is closed at eleven.

Outputs are deduplicated and emitted in a stable canonical order
so the persisted Signature row is byte-stable across runs.
"""
from __future__ import annotations


_CATEGORY_ORDER: tuple[str, ...] = (
    "webpack", "vite", "nextjs", "angular",
    "react", "vue", "svelte",
    "node_modules",
    "absolute_path", "relative_path", "url",
    "unknown",
)

_INDICATOR_ORDER: tuple[str, ...] = (
    "/src/", "/app/", "/components/", "/pages/",
    "/routes/", "/server/", "/api/",
    "C:\\", "/home/", "/Users/", "/builds/",
)


def categorise_sources(sources: list[str]) -> list[str]:
    """Map every entry in ``sources`` to one or more category labels,
    union the results, and return them in spec order."""
    hits: set[str] = set()
    for src in sources:
        hits.update(_categorise_one(src))
    return [c for c in _CATEGORY_ORDER if c in hits]


def find_internal_indicators(sources: list[str]) -> list[str]:
    """Substring-scan every source path for the spec's eleven
    internal-path indicators. Return matches in spec order."""
    hits: set[str] = set()
    for src in sources:
        for indicator in _INDICATOR_ORDER:
            if indicator in src:
                hits.add(indicator)
    return [i for i in _INDICATOR_ORDER if i in hits]


def _categorise_one(src: str) -> set[str]:
    """Deterministic per-source classification. Heuristics are
    substring-only — no parsing, no execution. Multiple categories
    can apply (e.g. a webpack:// node_modules entry → both)."""
    found: set[str] = set()
    lowered = src.lower()

    if lowered.startswith("webpack:"):
        found.add("webpack")
    if "vite:" in lowered or "/.vite/" in lowered:
        found.add("vite")
    if "/.next/" in lowered or "/_next/" in lowered:
        found.add("nextjs")
    if "/.angular/" in lowered or lowered.startswith("ng:"):
        found.add("angular")
    if "node_modules" in lowered:
        found.add("node_modules")
    if lowered.endswith((".tsx", ".jsx")) or "/react/" in lowered:
        found.add("react")
    if lowered.endswith(".vue") or "/vue/" in lowered:
        found.add("vue")
    if lowered.endswith(".svelte"):
        found.add("svelte")
    if lowered.startswith(("http://", "https://")):
        found.add("url")
    elif lowered.startswith(("./", "../")):
        found.add("relative_path")
    elif src.startswith("/") and not src.startswith("//"):
        found.add("absolute_path")

    if not found:
        found.add("unknown")
    return found
