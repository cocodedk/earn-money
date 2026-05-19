"""robots.txt path extractor for stub 1.6.

Pulls every `Disallow:` path from the body — these are the routes the
site operator explicitly told crawlers to skip, which makes them prime
hidden-route candidates. `Allow:` and `User-agent:` lines are ignored
for hidden-route purposes (the spec is route discovery, not crawler-
policy compliance).
"""
from __future__ import annotations


_DISALLOW_PREFIX = "disallow:"
# Defence-in-depth body cap — fetcher will also cap, but the
# extractor shouldn't blow memory if the contract gets relaxed.
_MAX_BODY_BYTES = 1_048_576


def parse_robots_txt(body: str) -> list[str]:
    paths: list[str] = []
    for raw in body[:_MAX_BODY_BYTES].splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.lower().startswith(_DISALLOW_PREFIX):
            continue
        value = line[len(_DISALLOW_PREFIX):].strip()
        if value:
            paths.append(value)
    return paths
