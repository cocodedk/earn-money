"""Framework-hint extractor for stub 1.15 (slice 4).

Spec §4 'Framework hints from deterministic strings'. Each match
against the closed signature table yields a ``FrameworkHint``; the
runner records all corroborating evidence rather than collapsing to
"the framework" — multiple patterns from the same framework all
land so confidence rules in slice 6 can lift from "low+low" to
"high" when two independent signals agree.

Substring match, case-sensitive. The signatures are spec-derived
unique tokens (React devtools hook, Vue globals, webpack runtime
internals, framework-specific URL prefixes). Pure function over
``body: str`` — no I/O, no parsing.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/15-public-javascript-bundles.md
"""
from __future__ import annotations

from typing import Literal, NamedTuple

from apps.stubs._shared.types import Confidence


FrameworkName = Literal[
    "react", "vue", "angular", "svelte",
    "nextjs", "nuxt", "vite", "webpack", "remix", "other",
]


class FrameworkHint(NamedTuple):
    name: FrameworkName
    matched_pattern: str
    confidence: Confidence


# Confidence assignments are framework-specific and chosen by signal
# uniqueness: framework-internal globals and protected URL prefixes
# are `high`; idiomatic-but-borrowable strings (`createApp(`,
# `react-dom`, `webpackJsonp`, `buildManifest`) are `medium`; and
# ambiguous shared tokens (`react`, `polyfills`, `vite/`) are `low`.
# Slice 6's confidence rules can combine multiple low/medium hits
# from the same framework into a stronger overall verdict.
_FRAMEWORK_SIGNATURES: tuple[tuple[FrameworkName, str, Confidence], ...] = (
    ("react", "__REACT_DEVTOOLS_GLOBAL_HOOK__", "high"),
    ("react", "data-reactroot", "high"),
    ("react", "react-dom", "medium"),
    ("react", "react", "low"),
    ("vue", "__VUE_DEVTOOLS_GLOBAL_HOOK__", "high"),
    ("vue", "__VUE__", "high"),
    ("vue", "createApp(", "medium"),
    ("angular", "ng-version", "high"),
    ("angular", "zone.js", "high"),
    ("angular", "webpackJsonp", "medium"),
    ("angular", "polyfills", "low"),
    ("svelte", "__svelte", "high"),
    ("svelte", "/_app/immutable/", "high"),
    ("svelte", "svelte", "medium"),
    ("nextjs", "__NEXT_DATA__", "high"),
    ("nextjs", "self.__next_f", "high"),
    ("nextjs", "/_next/static/", "high"),
    ("nuxt", "__NUXT__", "high"),
    ("nuxt", "/_nuxt/", "high"),
    ("vite", "import.meta.env", "high"),
    ("vite", "/@vite/", "high"),
    ("vite", "vite/", "low"),
    ("webpack", "__webpack_require__", "high"),
    ("webpack", "webpackChunk", "high"),
    ("remix", "__remixContext", "high"),
    ("remix", "buildManifest", "medium"),
)


def extract_framework_hints(body: str) -> list[FrameworkHint]:
    return [
        FrameworkHint(name, pattern, confidence)
        for name, pattern, confidence in _FRAMEWORK_SIGNATURES
        if pattern in body
    ]
