from __future__ import annotations

import json
import pytest
from apps.agent.llm.prompts import build_system_prompt, format_observation_message
from apps.agent.actions.matrix import allowed_actions_for_phase


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


class TestProbePromptSchemas:
    def test_probe_prompt_includes_click(self):
        prompt = build_system_prompt(
            objective="test",
            phase="probe",
            allowed_actions=allowed_actions_for_phase("probe"),
            budget_remaining=10,
        )
        assert "click" in prompt
        assert "element_id" in prompt

    def test_probe_prompt_includes_http_request(self):
        prompt = build_system_prompt(
            objective="test",
            phase="probe",
            allowed_actions=allowed_actions_for_phase("probe"),
            budget_remaining=10,
        )
        assert "http_request" in prompt
        assert '"method"' in prompt
        assert '"path"' in prompt

    def test_report_prompt_excludes_click(self):
        prompt = build_system_prompt(
            objective="test",
            phase="report",
            allowed_actions=allowed_actions_for_phase("report"),
            budget_remaining=5,
        )
        assert "click" not in prompt
        assert "http_request" not in prompt

    def test_all_phase_actions_have_schema_snippet(self):
        from apps.agent.llm.prompts import _ACTION_SCHEMA_SNIPPETS
        from apps.agent.actions.matrix import _PHASE_ACTION_MATRIX
        all_actions = set().union(*_PHASE_ACTION_MATRIX.values())
        missing = all_actions - set(_ACTION_SCHEMA_SNIPPETS)
        assert missing == set(), f"Actions missing schema snippets: {missing}"

    def test_enumerate_prompt_includes_fill_form(self):
        prompt = build_system_prompt(
            objective="test",
            phase="enumerate",
            allowed_actions=allowed_actions_for_phase("enumerate"),
            budget_remaining=10,
        )
        assert "fill_form" in prompt
        assert "element_id" in prompt

    @pytest.mark.parametrize("phase", ["probe", "verify"])
    def test_probe_and_verify_prompts_include_fill_and_submit_schemas(self, phase):
        prompt = build_system_prompt(
            objective="test",
            phase=phase,
            allowed_actions=allowed_actions_for_phase(phase),
            budget_remaining=10,
        )
        assert "fill_form" in prompt
        assert "submit_form" in prompt
        # submit_form must guide the LLM to use a button element ID, not a form ID
        assert "btn_0" in prompt

    def test_enumerate_prompt_includes_fill_schema_only(self):
        prompt = build_system_prompt(
            objective="test",
            phase="enumerate",
            allowed_actions=allowed_actions_for_phase("enumerate"),
            budget_remaining=10,
        )
        assert "fill_form" in prompt
        # submit_form is NOT in enumerate phase
        assert "submit_form" not in prompt


class TestPriorIntelSection:
    def _build(self, prior_intel_section=""):
        return build_system_prompt(
            objective=_OBJ,
            phase=_PHASE,
            allowed_actions=_ACTIONS,
            budget_remaining=_BUDGET,
            prior_intel_section=prior_intel_section,
        )

    def test_no_intel_omits_section(self):
        prompt = self._build()
        assert "## Prior Intel" not in prompt

    def test_intel_injected_when_provided(self):
        intel = "## Prior Intel\n- /admin returned 200 last run"
        prompt = self._build(prior_intel_section=intel)
        assert intel in prompt

    def test_intel_appears_after_budget_before_safety(self):
        intel = "## Prior Intel\n- /admin returned 200 last run"
        prompt = self._build(prior_intel_section=intel)
        budget_pos = prompt.index("Remaining turns")
        intel_pos = prompt.index("Prior Intel")
        safety_pos = prompt.index("Safety Rules")
        assert budget_pos < intel_pos < safety_pos
