"""Shared helpers for action-class tests."""
from __future__ import annotations

from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.probe_actions import GetAction, PostAction
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType


def _profile(**overrides: object) -> RoeProfile:
    defaults: dict[str, object] = dict(
        name="t",
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
    defaults.update(overrides)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


def _obs(status: int, url: str, ctype: str = "text/html", body: str = "ok") -> ObservationWrapper:
    return ObservationWrapper.from_response(status, url, {"Content-Type": ctype}, body)


def _get(path: str) -> GetAction:
    return GetAction.model_validate({"tool": "get", "category": "http_get", "args": {"path": path}})


def _post(path: str, json_body: dict | None = None) -> PostAction:
    return PostAction.model_validate({
        "tool": "post", "category": "http_post",
        "args": {"path": path, "json": json_body or {}},
    })
