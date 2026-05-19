"""Tolerant requirements.txt parser for stub 1.5.

Only emits findings for exact `pkg==version` pins. Lines with `>=`,
`~=`, `<`, etc. are constraints — not leaks of an exact installed
version — so they're skipped. Comments (`#`) and blanks are ignored.
"""
from __future__ import annotations

import re


_SOURCE_KIND = "requirements.txt"
# Common shapes covered:
#   foo==1.0
#   foo[extra]==1.0
#   foo==1.0 ; python_version >= '3.8'
#   foo[a,b]==1.0; sys_platform == 'linux'
# Extras and PEP 508 environment markers are ignored — we keep the
# package name + exact version. Hash-pinned lines (`pkg==1.0 --hash=...`)
# are out of MVP scope.
_PINNED_RE = re.compile(
    r"^\s*"
    r"([A-Za-z0-9][A-Za-z0-9_.\-]*)"   # package
    r"(?:\[[^\]]+\])?"                   # optional [extras]
    r"==([A-Za-z0-9.\-]+)"                # exact version
    r"\s*"
    r"(?:;.*)?"                          # optional PEP 508 marker
    r"$"
)


def parse_requirements_txt(body: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = _PINNED_RE.match(line)
        if m is None:
            continue
        hits.append(
            {
                "package": m.group(1),
                "version": m.group(2),
                "source_kind": _SOURCE_KIND,
            }
        )
    return hits
