"""Shared helpers for username_enum tests."""
from __future__ import annotations

from unittest.mock import MagicMock

from apps.programs.loader import Program
from apps.programs.roe import RoE
from apps.programs.scope import Scope


def _program(*, login_probes: bool = True, accounts: list[str] | None = None) -> Program:
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(
            max_requests_per_second=10,
            allow_active_login_probes=login_probes,
            authorized_test_accounts=accounts or [],
        ),
    )


def _mock_response(
    *,
    status: int = 200,
    body: str = "",
    content_type: str = "text/html",
    url: str = "https://x.example/login",
) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.headers = {"content-type": content_type}
    r.url = url
    return r
