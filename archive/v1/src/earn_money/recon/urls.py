"""URL helpers shared across recon and triage."""

from __future__ import annotations

from urllib.parse import urlparse


def target_host(target: str, fallback: str) -> str:
    """Extract the hostname from a URL for OOS scope checks.

    If `target` has no scheme or cannot be parsed, fall back to `fallback`
    (typically `sig.asset`) so callers get a consistent non-empty string.
    """
    if "://" in target:
        return urlparse(target).hostname or fallback
    return fallback
