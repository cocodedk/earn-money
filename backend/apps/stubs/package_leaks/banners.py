"""Banner-regex scanner for stub 1.5 package-version-leaks.

Minified JS/CSS bundles routinely carry license-banner comments
like `/*! lodash 4.17.21 */` that disclose package + version. The
scanner anchors on the JS comment markers (`/*!` or `/**`) so
prose mentioning a version number doesn't fire as a false positive.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/05-package-version-leaks.md
"""
from __future__ import annotations

import re


# A banner comment starts with `/*!` (bang for "preserve") or `/**`
# (jsdoc). Inside, look for a package-like token (npm scope optional)
# followed by a version-like token (optional `v` prefix, dotted
# digits). The `.*?` is non-greedy so the regex matches the smallest
# string between `/*` and `*/` — won't span unrelated banners. DOTALL
# lets the inner window cross the `*`-prefixed lines of multi-line
# banners (`/*!\n * react 17.0.2\n */`).
_BANNER_RE = re.compile(
    r"/\*[!*]"
    r".*?"
    r"(@?[a-zA-Z][a-zA-Z0-9_./\-]*)"  # package name (scoped names ok)
    r"\s+"
    r"v?(\d+\.\d+(?:\.\d+)?)"          # version: x.y or x.y.z
    r".*?"
    r"\*/",
    re.DOTALL,
)

# Reserved words common in license banners we don't want to treat as
# package names. Filters @license / @version / etc. when they happen
# to land in the package-name capture group.
_RESERVED_NAME_PREFIXES = {"@license", "@version", "Copyright", "License"}


def scan_banners(text: str) -> list[dict[str, str]]:
    """Return [{package, version}] for every banner-like comment that
    contains a package + version pair."""
    hits: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in _BANNER_RE.finditer(text):
        package = match.group(1)
        version = match.group(2)
        if package in _RESERVED_NAME_PREFIXES:
            continue
        key = (package, version)
        if key in seen:
            continue
        seen.add(key)
        hits.append({"package": package, "version": version})
    return hits
