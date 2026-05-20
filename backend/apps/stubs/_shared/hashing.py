"""Body-hash helpers for soft-404 + content_hash use across stubs.

Two flavours because Evidence.content_hash in stub 1.1 carries the
`sha256:` prefix (consumed by triage tooling that splits on the
colon to identify the algorithm), while soft-404 hash sets in stubs
1.6/1.8 use the raw hex digest for set-membership tests.
"""
from __future__ import annotations

import hashlib


def body_hash(text: str) -> str:
    """Raw hex SHA-256 of `text` (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def body_hash_bytes(data: bytes) -> str:
    """Raw hex SHA-256 of `data`. Bytes flavour for callers (stub 1.15
    fetcher) that work in wire bytes so the hash is independent of
    UTF-8 decoding decisions."""
    return hashlib.sha256(data).hexdigest()


def prefixed_body_hash(text: str) -> str:
    """Return `sha256:<hex>` — the format Evidence.content_hash carries
    so downstream tooling can split on `:` to recover the algorithm."""
    return f"sha256:{body_hash(text)}"
