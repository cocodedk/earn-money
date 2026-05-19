"""robots.txt path extractor for stub 1.6.

Thin projection over stub 1.11's structured `parse_robots()`: pulls
every `Disallow:` value across every robots group into a flat list
of paths. `Allow:` and `User-agent:` lines are ignored for hidden-
route purposes (the spec is route discovery, not crawler-policy
compliance).

Behaviour vs the pre-#105 implementation: full external URLs in
Disallow values are now dropped, since `parse_robots`'s path-hint
filter (spec §Path normalization rule 2) rejects them. Stub 1.6
never wanted to probe external URLs anyway — they were operator
noise.
"""
from __future__ import annotations

from ...robots_txt.parser import parse_robots


# Defence-in-depth body cap — stub 1.6's fetcher already caps the
# body, but the extractor shouldn't blow memory if the contract
# gets relaxed. Carried forward from the pre-#105 implementation.
_MAX_BODY_BYTES = 1_048_576


def parse_robots_txt(body: str) -> list[str]:
    parsed = parse_robots(body[:_MAX_BODY_BYTES])
    paths: list[str] = []
    for group in parsed.groups:
        paths.extend(group.disallows)
    return paths
