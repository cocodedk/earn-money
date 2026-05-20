"""Tolerant package.json parser for stub 1.5.

Extracts top-level name+version + dependencies + devDependencies as
(package, version) tuples. Malformed JSON degrades to an empty list
rather than raising — the runner shouldn't crash on adversarial input.
"""
from __future__ import annotations

import json


_SOURCE_KIND = "package.json"


def parse_package_json(body: str) -> list[dict[str, str]]:
    """Return [{package, version, source_kind}] extracted from the body.

    Returns [] on any parse failure. Non-string version values are
    skipped (a package.json with `"version": 1.0` instead of `"1.0"`
    is malformed; don't fabricate a version)."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []

    hits: list[dict[str, str]] = []
    _maybe_append_root(data, hits)
    for section in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
        "bundledDependencies",
    ):
        _maybe_append_deps(data.get(section), hits)
    return hits


def _maybe_append_root(data: dict, hits: list[dict[str, str]]) -> None:
    name = data.get("name")
    version = data.get("version")
    if isinstance(name, str) and isinstance(version, str):
        hits.append(
            {"package": name, "version": version, "source_kind": _SOURCE_KIND}
        )


def _maybe_append_deps(
    deps: object, hits: list[dict[str, str]]
) -> None:
    if not isinstance(deps, dict):
        return
    for name, version in deps.items():
        if isinstance(name, str) and isinstance(version, str):
            hits.append(
                {
                    "package": name,
                    "version": version,
                    "source_kind": _SOURCE_KIND,
                }
            )
