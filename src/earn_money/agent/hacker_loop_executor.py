"""Action executor + observation recorder for the HackerLoop.

Extracted from hacker_loop.py to keep that module under the project's
200-line file cap. These two helpers branch on the parsed Action type
and apply side effects (HTTP probe, session mutation, finding-verifier
evaluation). They take the loop instance explicitly so they remain
pure functions; the calling code passes `self` from `HackerLoop.run`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.probe_actions import (
    GetAction,
    PostAction,
    ReportCandidateAction,
    SetHeaderAction,
    StoreAction,
)

if TYPE_CHECKING:
    from .hacker_loop import HackerLoop


def execute_action(
    loop: HackerLoop,
    action: GetAction | PostAction | SetHeaderAction | StoreAction | ReportCandidateAction,
) -> None:
    if isinstance(action, GetAction):
        obs = loop.http_tool.get(action.args.path, action.args.params)
        loop._on_observation(loop._current_turn, action, obs)
        record_observation(loop, action, obs)
    elif isinstance(action, PostAction):
        obs = loop.http_tool.post(
            action.args.path,
            json_body=action.args.json_body,
            data=action.args.data,
        )
        loop._on_observation(loop._current_turn, action, obs)
        record_observation(loop, action, obs)
    elif isinstance(action, SetHeaderAction):
        loop.http_tool.set_header(action.args.name, action.args.value)
    elif isinstance(action, StoreAction):
        if action.args.kind == "token":
            loop.session.store_token(action.args.key, action.args.value)
        else:
            loop.session.store_id(action.args.key, action.args.value)
    elif isinstance(action, ReportCandidateAction):
        loop.session.add_candidate_finding(action.args.model_dump())


def record_observation(
    loop: HackerLoop, action: GetAction | PostAction, obs: ObservationWrapper,
) -> None:
    loop.session.add_observation(obs)
    candidates, verified = loop.verifier.evaluate(action.model_dump(), obs, loop.session)
    for c in candidates:
        loop._on_finding(loop._current_turn, "candidate", c)
        loop.session.add_candidate_finding(c)
    for v in verified:
        loop._on_finding(loop._current_turn, "verified", v)
        loop.session.add_verified_finding(v)
