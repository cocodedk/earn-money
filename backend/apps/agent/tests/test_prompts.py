from __future__ import annotations

import json
import pytest
from apps.agent.llm.prompts import build_system_prompt, format_observation_message


_OBJ = "Find the hidden scoreboard page."
_PHASE = "recon"
_ACTIONS = ["observe_page", "navigate", "stop"]
_BUDGET = 15


class TestBuildSystemPrompt:
    def _build(self, **kwargs):
        defaults = dict(
            objective=_OBJ,
            phase=_PHASE,
            allowed_actions=_ACTIONS,
            budget_remaining=_BUDGET,
        )
        defaults.update(kwargs)
        return build_system_prompt(**defaults)

    def test_returns_string(self):
        assert isinstance(self._build(), str)

    def test_objective_in_prompt(self):
        prompt = self._build()
        assert _OBJ in prompt

    def test_phase_in_prompt(self):
        prompt = self._build()
        assert _PHASE in prompt

    def test_budget_remaining_in_prompt(self):
        prompt = self._build()
        assert str(_BUDGET) in prompt

    def test_all_allowed_actions_listed(self):
        prompt = self._build()
        for action in _ACTIONS:
            assert action in prompt

    def test_sorted_action_list(self):
        prompt = self._build(allowed_actions=["stop", "navigate", "observe_page"])
        nav_pos = prompt.index("navigate")
        obs_pos = prompt.index("observe_page")
        stop_pos = prompt.index("stop")
        # sorted: navigate < observe_page < stop
        assert nav_pos < obs_pos < stop_pos

    def test_untrusted_content_fencing_present(self):
        prompt = self._build()
        assert "UNTRUSTED" in prompt or "untrusted" in prompt.lower()

    def test_safety_rules_present(self):
        prompt = self._build()
        assert "Safety" in prompt or "MUST NOT" in prompt

    def test_action_schemas_present(self):
        prompt = self._build()
        assert "observe_page" in prompt
        assert "navigate" in prompt


class TestFormatObservationMessage:
    def test_observation_dict_wrapped(self):
        obs = {"identity": {"url": "https://example.com/"}, "trust": "untrusted_target_content"}
        msg = format_observation_message(obs_dict=obs)
        assert "untrusted_target_content" in msg
        assert "https://example.com/" in msg

    def test_observation_wrapped_in_tag(self):
        msg = format_observation_message(obs_dict={"x": 1})
        assert "<observation" in msg
        assert "</observation>" in msg

    def test_observation_trust_attribute(self):
        msg = format_observation_message(obs_dict={"x": 1})
        assert 'trust="untrusted_target_content"' in msg

    def test_denial_wrapped_in_tag(self):
        msg = format_observation_message(denial_reason="Action not allowed in phase")
        assert "<denial>" in msg
        assert "</denial>" in msg

    def test_denial_includes_reason(self):
        reason = "Action not allowed in phase"
        msg = format_observation_message(denial_reason=reason)
        assert reason in msg

    def test_neither_returns_empty(self):
        msg = format_observation_message()
        assert msg == ""

    def test_denial_takes_precedence_over_obs(self):
        msg = format_observation_message(
            obs_dict={"x": 1},
            denial_reason="blocked",
        )
        assert "<denial>" in msg
        assert "<observation" not in msg

    def test_observation_content_is_json(self):
        obs = {"key": "value", "num": 42}
        msg = format_observation_message(obs_dict=obs)
        # JSON content should be parseable from the message
        assert '"key"' in msg
        assert '"value"' in msg
