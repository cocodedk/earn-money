"""Soft-404 baseline detector contract.

The detector probes one definitely-nonexistent path per target,
fingerprints (status, length-bucket, body-prefix-hash), and rejects
subsequent candidates whose responses match.

Spec sources: 1.20 / 1.22 / 1.23 §False-positive controls.
"""
from __future__ import annotations

from apps.stubs.well_known_paths import soft_404


def test_random_path_is_unique_and_safe() -> None:
    a = soft_404.random_nonexistent_path()
    b = soft_404.random_nonexistent_path()
    assert a != b
    assert a.startswith("/")
    assert "__scanner_nonexistent_" in a


def test_footprint_matches_identical_response() -> None:
    body = b"<!DOCTYPE html><html><body>Page not found</body></html>"
    fp = soft_404.footprint_for(status=200, body=body)
    assert soft_404.matches_soft_404(fp, status=200, body=body) is True


def test_footprint_rejects_different_status() -> None:
    body = b"<!DOCTYPE html><html><body>x</body></html>"
    fp = soft_404.footprint_for(status=200, body=body)
    assert soft_404.matches_soft_404(fp, status=404, body=body) is False


def test_footprint_rejects_different_body_prefix() -> None:
    fp = soft_404.footprint_for(
        status=200, body=b"<!DOCTYPE html><html><body>Hello</body></html>",
    )
    assert soft_404.matches_soft_404(
        fp, status=200,
        body=b"DB_PASSWORD=secret\nAPI_KEY=abc123",
    ) is False


def test_footprint_tolerates_suffix_jitter_within_bucket() -> None:
    """Two responses with IDENTICAL first 256 bytes and lengths in the
    SAME 64-byte bucket should match — defends against suffix-only
    jitter (e.g. trailing nonces, timestamps) in SPA shells.

    Differing prefixes always mean a different footprint, regardless
    of length-bucket: the prefix hash is over the raw first-256 bytes.
    """
    base = b"x" * 500  # length-bucket = (500 // 64) * 64 = 448; prefix = 256 'x's
    fp = soft_404.footprint_for(status=200, body=base)
    # Same prefix, length still in bucket 448 → match.
    assert soft_404.matches_soft_404(fp, status=200, body=b"x" * 510) is True
    # Different bucket (length 600 → bucket 576) → no match.
    assert soft_404.matches_soft_404(fp, status=200, body=b"x" * 600) is False
    # Different prefix even with same length → no match.
    different_prefix = b"y" * 256 + b"x" * 244
    assert soft_404.matches_soft_404(fp, status=200, body=different_prefix) is False
