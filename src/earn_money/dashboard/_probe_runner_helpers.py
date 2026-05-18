"""Pure helpers for ProbeRunner — RoE-profile mutators, task-router
fallback, token estimator, run-result summariser. Extracted so the
runner module stays under the project's 200-line file cap; ProbeRunner
imports these but they have no thread or queue state of their own.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from earn_money.agent.roe_profile import RoeProfile
from earn_money.agent.task_router import RouterUnconfigured, TaskType, resolve_model


def _augment_with_base_host(profile: RoeProfile, base_url: str) -> RoeProfile:
    host = urlparse(base_url).hostname
    if not host or host in profile.allowed_hosts:
        return profile
    data = profile.model_dump(exclude={"source_type", "source_ref"})
    data["allowed_hosts"] = [*profile.allowed_hosts, host]
    return RoeProfile.from_dict(data, profile.source_type, profile.source_ref)


def _apply_max_turns(profile: RoeProfile, max_turns: int) -> RoeProfile:
    # TODO: share with hacker_loop_cli._apply_cli_limits once that helper
    # is refactored to take a dict of overrides (out of scope for this PR).
    effective = min(profile.max_turns, max_turns)
    data = profile.model_dump(exclude={"source_type", "source_ref"})
    data["max_turns"] = effective
    return RoeProfile.from_dict(data, profile.source_type, profile.source_ref)


def _resolve_model_safely(task: TaskType) -> str | None:
    try:
        return resolve_model(task)
    except RouterUnconfigured:
        return None


def _est_tokens(text: str | None) -> int:
    return (len(text) // 4) if text else 0


def _summarise(result: Any) -> dict[str, Any]:
    return {
        "turns": result.turns,
        "stop_reason": result.stop_reason,
        "candidates_count": len(result.candidate_findings),
        "verified_count":   len(result.verified_findings),
        "denials_count":    len(result.policy_denials),
    }
