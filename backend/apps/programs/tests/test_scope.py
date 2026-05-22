"""Scope-matcher contract for stub `apps.programs.scope`.

Coverage matrix per [[plan slice A]]:
- exact / wildcard / wildcard does NOT match bare apex
- out-of-scope override / port-agnostic
- case-insensitive / trailing-dot strip / IDNA normalization
- malformed host rejects closed
"""
from __future__ import annotations

import pytest

from apps.programs.scope import matches_scope


# --- exact match ---


def test_exact_match() -> None:
    assert matches_scope("www.algolia.com", ["www.algolia.com"], []) is True


def test_exact_match_misses_subdomain() -> None:
    assert matches_scope("api.algolia.com", ["www.algolia.com"], []) is False


# --- wildcard match ---


def test_wildcard_matches_one_level() -> None:
    assert matches_scope("dashboard.algolia.net", ["*.algolia.net"], []) is True


def test_wildcard_matches_deep_subdomain() -> None:
    assert matches_scope("x.y.algolia.net", ["*.algolia.net"], []) is True


def test_wildcard_does_not_match_bare_apex() -> None:
    """Deliberate v2 divergence from v1: `*.algolia.net` does not match
    `algolia.net`. Tightens wildcards per decision-doc."""
    assert matches_scope("algolia.net", ["*.algolia.net"], []) is False


# --- out-of-scope override ---


def test_out_of_scope_overrides_in_scope() -> None:
    assert matches_scope(
        "leak.algolia.net",
        in_scope=["*.algolia.net"],
        out_of_scope=["leak.algolia.net"],
    ) is False


def test_out_of_scope_wildcard_overrides_in_scope_wildcard() -> None:
    assert matches_scope(
        "internal.api.algolia.net",
        in_scope=["*.algolia.net"],
        out_of_scope=["*.internal.algolia.net", "internal.api.algolia.net"],
    ) is False


# --- normalization: lower-case / trailing dot / port-agnostic ---


def test_lower_cases_input_host() -> None:
    assert matches_scope("WWW.Algolia.com", ["www.algolia.com"], []) is True


def test_lower_cases_pattern() -> None:
    assert matches_scope("www.algolia.com", ["WWW.algolia.COM"], []) is True


def test_strips_one_trailing_dot() -> None:
    assert matches_scope("www.algolia.com.", ["www.algolia.com"], []) is True


def test_idna_normalises_unicode_input() -> None:
    """Punycode roundtrip — Unicode input must normalise to the
    canonical Punycode form before matching."""
    # `algoliá.com` IDNA-encodes to `xn--algoli-uta.com`.
    assert matches_scope("algoliá.com", ["xn--algoli-uta.com"], []) is True


# --- port-agnostic: matcher accepts hosts only, not host:port ---


def test_rejects_host_with_port() -> None:
    """`matches_scope()` accepts hostnames only; URL parsing happens
    upstream in `scope_check.enforce_scope`. Port-stripping is NOT
    this function's job — host:port is a malformed host input."""
    with pytest.raises(ValueError):
        matches_scope("www.algolia.com:443", ["www.algolia.com"], [])


# --- malformed-host rejection ---


def test_rejects_empty_host() -> None:
    with pytest.raises(ValueError):
        matches_scope("", ["www.algolia.com"], [])


def test_rejects_host_with_path() -> None:
    with pytest.raises(ValueError):
        matches_scope("www.algolia.com/admin", ["www.algolia.com"], [])


def test_rejects_host_with_scheme() -> None:
    with pytest.raises(ValueError):
        matches_scope("https://www.algolia.com", ["www.algolia.com"], [])


def test_rejects_host_that_normalises_to_empty() -> None:
    """A host of `.` normalises to empty after rstrip — covers the
    post-normalisation empty-host raise."""
    with pytest.raises(ValueError):
        matches_scope(".", ["www.algolia.com"], [])


def test_rejects_idna_unencodable_host() -> None:
    """Labels exceeding the 63-octet DNS limit fail IDNA encode."""
    long_label = "a" * 64
    with pytest.raises(ValueError):
        matches_scope(f"{long_label}.example.com", ["example.com"], [])
