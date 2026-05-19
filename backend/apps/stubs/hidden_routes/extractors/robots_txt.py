"""robots.txt path extractor for stub 1.6.

Pulls every `Disallow:` path from the body — these are the routes the
site operator explicitly told crawlers to skip, which makes them prime
hidden-route candidates. `Allow:` and `User-agent:` lines are ignored
for hidden-route purposes (the spec is route discovery, not crawler-
policy compliance).
"""
from __future__ import annotations


_DISALLOW_PREFIX = "disallow:"


def parse_robots_txt(body: str) -> list[str]:
    paths: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.lower().startswith(_DISALLOW_PREFIX):
            continue
        value = line[len(_DISALLOW_PREFIX):].strip()
        if value:
            paths.append(value)
    return paths
