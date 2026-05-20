"""Shared exception types for `apps.programs` and downstream consumers.

One module so loader / scans / stubs all import from the same place
instead of creating local copies. Each exception is narrow enough that
callers can catch one specific failure mode without swallowing
unrelated bugs.
"""
from __future__ import annotations


class InvalidScope(Exception):
    """Raised when `scope.md` or `roe.md` is malformed (bad YAML,
    missing required key, unknown policy value)."""


class OutOfScope(Exception):
    """Raised when a host is not in any registered program's scope, or
    when a candidate URL falls outside the resolved program's scope."""


class ManualOnly(Exception):
    """Raised when a program's policy is `manual-only` — active
    runners refuse to start."""


class AmbiguousPolicy(Exception):
    """Raised when a program's policy is `ambiguous` — active
    runners refuse to start; reserved for passive recon."""


class AmbiguousProgram(Exception):
    """Raised when a host matches two or more programs with equal
    specificity (e.g. both have `*.example.com` in_scope). Pre-flight
    refuses; operator must disambiguate via out_of_scope."""


class ReconDisabled(Exception):
    """Raised when the `RECON_ENABLED` flag-file is absent (or is a
    directory). Master kill-switch."""


class ProgramFrozen(Exception):
    """Raised when `programs/<platform>/<slug>/FROZEN` exists. Per-
    program kill-switch."""
