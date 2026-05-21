"""Unit tests for `_shared/scope_check.is_in_scope` — pure predicate,
no side effects. Used by fetchers that gate redirect hops without
spamming OUT_OF_SCOPE_REJECTED events.
"""
from __future__ import annotations

from apps.programs.loader import Program
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.scope_check import is_in_scope


def _program(
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> Program:
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=in_scope or ["x.example"],
            out_of_scope=out_of_scope or [],
        ),
        roe=RoE(max_requests_per_second=10),
    )


def test_is_in_scope_true_for_in_scope_host() -> None:
    assert is_in_scope("https://x.example/path", _program()) is True


def test_is_in_scope_false_for_out_of_scope_host() -> None:
    assert is_in_scope("https://attacker.example/", _program()) is False


def test_is_in_scope_false_for_denied_host_even_if_in_scope() -> None:
    program = _program(out_of_scope=["danger.x.example"])
    assert is_in_scope("https://danger.x.example/", program) is False


def test_is_in_scope_false_for_malformed_url() -> None:
    assert is_in_scope("not-a-url", _program()) is False


def test_is_in_scope_false_for_non_http_scheme() -> None:
    assert is_in_scope("ftp://x.example/", _program()) is False
