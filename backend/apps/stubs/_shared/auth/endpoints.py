"""Bounded candidate-path lists for auth-flow discovery.

The crawler should be the authoritative source of auth endpoints. These
fallback lists exist for `allow_common_login_path_probe=True` cases per
spec 2.1 §1 step 4: bounded GET probes against well-known paths when no
endpoint was discovered.

Hints, not technology assumptions. The runner still decides from
response evidence (form structure, JSON shape, response title) whether
a path is actually an auth surface. Candidate hits without form evidence
emit no Finding.

Returned lists are fresh copies — callers cannot mutate the canonical
set held in this module.
"""
from __future__ import annotations


_LOGIN_PATHS: tuple[str, ...] = (
    "/login",
    "/signin",
    "/sign-in",
    "/account/login",
    "/user/login",
    "/auth/login",
    "/admin/login",
)

_RESET_PATHS: tuple[str, ...] = (
    "/password-reset",
    "/reset-password",
    "/forgot-password",
    "/account/recover",
    "/auth/reset",
)

_REGISTER_PATHS: tuple[str, ...] = (
    # JSON API variants first — modern targets answer here.
    "/api/Users",          # Juice Shop
    "/api/register",
    "/api/v1/register",
    "/api/auth/register",
    # HTML form-action variants.
    "/register",
    "/signup",
    "/sign-up",
    "/account/create",
    "/auth/register",
)


def candidate_login_paths() -> list[str]:
    """Bounded set of well-known login URL paths."""
    return list(_LOGIN_PATHS)


def candidate_reset_paths() -> list[str]:
    """Bounded set of well-known password-reset URL paths."""
    return list(_RESET_PATHS)


def candidate_register_paths() -> list[str]:
    """Bounded set of well-known registration URL paths."""
    return list(_REGISTER_PATHS)
