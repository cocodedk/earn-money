"""Tolerant requirements.txt parser for stub 1.5.

Only emits findings for exact `pkg==version` pins. Lines with `>=`,
`~=`, `<`, etc. are constraints — not leaks of an exact installed
version — so they're skipped. Comments (`#`) and blanks are ignored.
"""
from __future__ import annotations

import re


_SOURCE_KIND = "requirements.txt"
_PINNED_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9_.\-]*)==([A-Za-z0-9.\-]+)\s*$"
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
