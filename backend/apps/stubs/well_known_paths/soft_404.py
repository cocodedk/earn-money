"""Soft-404 baseline detector for stub `well_known_paths`.

Many SPAs and CDNs return a generic 200 response (often the app shell)
for ANY path that doesn't resolve to a real asset. Without soft-404
detection the scanner would emit findings on every probed candidate
path. The defense: probe ONE definitely-nonexistent random path per
target, hash the response shape, and reject subsequent candidates
that produce a matching shape.

Per the Phase 1 closeout plan: this control is NEW to WKP. Lift to
`_shared/soft_404.py` deferred until a 2nd consumer arrives.

Spec sources: 1.20 / 1.22 / 1.23 §False-positive controls.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import NamedTuple


_BUCKET_SIZE = 64  # round content-length to the nearest 64 bytes
_PREFIX_BYTES = 256


class SoftFootprint(NamedTuple):
    """A compact, stable fingerprint of a 'definitely-nonexistent'
    response. Two responses match if all three components agree.
    """
    status: int
    length_bucket: int
    body_prefix_hash: str


def random_nonexistent_path() -> str:
    """Return a path that no real app would resolve.

    The token is high-entropy so the chance of collision with a real
    route is negligible.
    """
    return f"/__scanner_nonexistent_{secrets.token_hex(8)}__"


def footprint_for(*, status: int, body: bytes) -> SoftFootprint:
    """Build a footprint from a response. Used to seed the baseline
    AND to test candidate responses against it.
    """
    length_bucket = (len(body) // _BUCKET_SIZE) * _BUCKET_SIZE
    prefix = body[:_PREFIX_BYTES]
    body_prefix_hash = hashlib.sha256(prefix).hexdigest()[:16]
    return SoftFootprint(
        status=status,
        length_bucket=length_bucket,
        body_prefix_hash=body_prefix_hash,
    )


def matches_soft_404(
    footprint: SoftFootprint, *, status: int, body: bytes,
) -> bool:
    """True when the candidate response matches the baseline footprint
    (likely a soft-404)."""
    candidate = footprint_for(status=status, body=body)
    return candidate == footprint
