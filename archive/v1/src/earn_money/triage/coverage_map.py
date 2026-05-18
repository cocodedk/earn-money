"""Coverage map loading and verdict helpers for the disclosure-replay benchmark.

Extracted from benchmark_score.py — provides CoverageMap, CoverageEntry, the
two exception classes, load_coverage_map(), and the truth-table helper
_verdict_for().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from earn_money import config


class CoverageMapNotFound(FileNotFoundError):
    """Raised when `benchmarks/coverage_map.yaml` is missing."""


class CoverageMapVersionMismatch(Exception):
    """Raised when --assert-coverage-map-version disagrees with the YAML."""


@dataclass(frozen=True)
class CoverageEntry:
    vuln_class: str
    plugins: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class CoverageMap:
    version: int
    entries: dict[str, CoverageEntry]


def load_coverage_map(paths: config.Paths) -> CoverageMap:
    """Read benchmarks/coverage_map.yaml and validate the version field."""
    p = paths.root / "benchmarks" / "coverage_map.yaml"
    if not p.exists():
        raise CoverageMapNotFound(str(p))
    data: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    version_raw = data.get("coverage_map_version")
    if not isinstance(version_raw, int):
        raise ValueError(
            f"coverage_map.yaml: coverage_map_version must be integer, "
            f"got {type(version_raw).__name__}"
        )
    entries: dict[str, CoverageEntry] = {}
    for raw in data.get("coverage") or []:
        cls = str(raw["vuln_class"])
        entries[cls] = CoverageEntry(
            vuln_class=cls,
            plugins=tuple(raw.get("plugins") or ()),
            notes=str(raw.get("notes") or ""),
        )
    return CoverageMap(version=version_raw, entries=entries)


# Truth-table verdict per (has_plugins, hint).
_FN_HINTS = frozenset({"requires-auth", "requires-business-logic",
                       "requires-payload-crafting"})
_INCONCLUSIVE_HINTS = frozenset({"regex-friendly", "requires-chain",
                                 "requires-fuzzing", "unclear"})


def _verdict_for(vuln_class: str, hint: str, cmap: CoverageMap) -> tuple[str, str]:
    """Apply the truth table from the spec. Returns (verdict, reason)."""
    entry = cmap.entries.get(vuln_class)
    if entry is None or not entry.plugins:
        return ("FN", f"no plugin covers {vuln_class}")
    plugins_str = ", ".join(entry.plugins)
    if hint in _FN_HINTS:
        return ("FN", f"plugin(s) [{plugins_str}] cover {vuln_class} class but "
                      f"hint={hint} requires capability we lack")
    if hint in _INCONCLUSIVE_HINTS:
        return ("inconclusive", f"plugin(s) [{plugins_str}] cover {vuln_class}; "
                                f"hint={hint} — operator review needed")
    return ("inconclusive", f"plugin(s) [{plugins_str}] cover {vuln_class}; "
                            f"hint={hint!r} unrecognised — operator review needed")
