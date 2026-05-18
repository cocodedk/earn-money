"""Shared helpers for hacker_loop test splits."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from earn_money.agent.budget import RequestBudget
from earn_money.agent.finding_verifier import FindingVerifier
from earn_money.agent.hacker_loop import HackerLoop
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.http_tool import HttpTool
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType
from earn_money.agent.scope_policy import ScopePolicy


def _profile(**kwargs: object) -> RoeProfile:
    defaults = dict(
        name="test",
        source_type=RoeSourceType.MANUAL,
        allowed_hosts=["target.example.com"],
        max_requests=100,
        max_posts=20,
        max_turns=10,
        max_runtime_seconds=60,
        max_response_bytes=5000,
        delay_between_requests_ms=0,
        allow_get=True,
        allow_post=True,
        allow_idor_checks=True,
    )
    defaults.update(kwargs)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


def _obs(status: int = 200, body: str = "ok") -> ObservationWrapper:
    return ObservationWrapper.from_response(status, "https://target.example.com/api", {}, body)


def _loop(
    provider_responses: list[str], *, presolved: bool = True, **profile_kwargs: object,
) -> HackerLoop:
    """Build a HackerLoop with a MagicMock provider for tests.

    `presolved=True` (default) pre-marks every probe class as tried on
    the session so a single-STOP-on-turn-1 fixture is still valid. Tests
    that exercise the STOP-validation logic itself should pass
    `presolved=False`.
    """
    from earn_money.agent.action_classes import ActionClass

    profile = _profile(**profile_kwargs)
    roe_policy = RoePolicy(profile)
    ScopePolicy(profile, "https://target.example.com")
    budget = RequestBudget(profile)
    session = HackerSession()
    if presolved:
        session.tried_action_classes = set(ActionClass)
    verifier = FindingVerifier(profile)

    http_tool = MagicMock(spec=HttpTool)
    http_tool.get.return_value = _obs()
    http_tool.post.return_value = _obs()
    http_tool.budget = budget

    provider = MagicMock()
    responses = iter(provider_responses)
    provider.complete.side_effect = lambda **kw: next(responses)

    return HackerLoop(profile, roe_policy, http_tool, budget, session, verifier, provider)


def _j(**kwargs: object) -> str:
    return json.dumps(kwargs)


def _provider_error(msg: str, *, status: int) -> Exception:
    """Mirror the production shape: a raised object carrying `.status_code`,
    same way the openai SDK / providers_openai_compat wraps HTTP failures."""
    from earn_money.agent.providers_openai_compat import ProviderError
    return ProviderError(msg, status_code=status)
