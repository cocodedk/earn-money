"""Shared pre/post login session-cookie comparison for stubs 3.5 and 3.6."""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.stubs._shared.session.cookie_parser import ParsedCookie, Sensitivity


@dataclass(frozen=True)
class CompareResult:
    fixed_names: list[str]
    no_pre_cookie: bool


def compare_session_cookies(
    pre_cookies: list[ParsedCookie],
    post_cookies: list[ParsedCookie],
) -> CompareResult:
    pre_session = {
        c.name: c.value_redacted
        for c in pre_cookies
        if c.sensitivity != Sensitivity.LOW and c.value_redacted is not None
    }
    if not pre_session:
        return CompareResult(fixed_names=[], no_pre_cookie=True)

    post_session = {
        c.name: c.value_redacted
        for c in post_cookies
        if c.sensitivity != Sensitivity.LOW and c.value_redacted is not None
    }

    fixed = [
        name for name, pre_val in pre_session.items()
        if post_session.get(name) == pre_val
    ]
    return CompareResult(fixed_names=fixed, no_pre_cookie=False)
