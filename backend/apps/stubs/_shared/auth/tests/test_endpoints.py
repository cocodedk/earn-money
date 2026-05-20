"""Contract tests for `_shared/auth/endpoints.candidate_*_paths`.

The candidate path lists are pure data. These tests lock in the
exact strings so a rename or accidental deletion is a visible
diff, not a silent reduction of probe coverage.
"""
from __future__ import annotations

import pytest

from apps.stubs._shared.auth.endpoints import (
    candidate_login_paths,
    candidate_register_paths,
    candidate_reset_paths,
)


def test_login_paths_includes_canonical_set() -> None:
    """Per spec 2.1 §1 — the bounded login candidate set."""
    paths = candidate_login_paths()
    assert "/login" in paths
    assert "/signin" in paths
    assert "/sign-in" in paths
    assert "/account/login" in paths
    assert "/user/login" in paths
    assert "/auth/login" in paths
    assert "/admin/login" in paths


def test_reset_paths_includes_canonical_set() -> None:
    paths = candidate_reset_paths()
    assert "/password-reset" in paths
    assert "/reset-password" in paths
    assert "/forgot-password" in paths
    assert "/account/recover" in paths
    assert "/auth/reset" in paths


def test_register_paths_includes_canonical_set() -> None:
    paths = candidate_register_paths()
    assert "/register" in paths
    assert "/signup" in paths
    assert "/sign-up" in paths
    assert "/account/create" in paths
    assert "/auth/register" in paths


@pytest.mark.parametrize(
    "candidates",
    [
        candidate_login_paths(),
        candidate_reset_paths(),
        candidate_register_paths(),
    ],
)
def test_paths_are_absolute_and_non_empty(candidates) -> None:
    """Every path starts with `/` and has non-trivial body so urljoin
    against a base produces a clean candidate URL."""
    assert candidates, "candidate list must be non-empty"
    for p in candidates:
        assert isinstance(p, str)
        assert p.startswith("/"), p
        assert len(p) > 1, p


def test_paths_have_no_duplicates() -> None:
    """A duplicate in the list would double-probe a target and burn
    rate-limit budget for no signal."""
    for getter in (
        candidate_login_paths, candidate_reset_paths, candidate_register_paths,
    ):
        paths = getter()
        assert len(paths) == len(set(paths)), (
            f"duplicate path in {getter.__name__}: "
            f"{[p for p in paths if paths.count(p) > 1]}"
        )


def test_returned_lists_are_immutable_snapshots() -> None:
    """Caller mutations must not pollute the canonical list shared
    across every stub invocation."""
    a = candidate_login_paths()
    a.append("/sneaky-injected")
    b = candidate_login_paths()
    assert "/sneaky-injected" not in b
