from __future__ import annotations

import pytest
from apps.agent.mission_profiles import (
    get_profile, resolve_model_policy, MissionProfile, _PROFILES,
)


class TestGetProfile:
    def test_returns_mission_profile_instance(self):
        profile = get_profile("juice_shop_scoreboard")
        assert isinstance(profile, MissionProfile)

    def test_unknown_profile_raises_key_error(self):
        with pytest.raises(KeyError, match="unknown_profile"):
            get_profile("unknown_profile")

    def test_error_message_lists_available(self):
        with pytest.raises(KeyError, match="juice_shop_scoreboard"):
            get_profile("nonexistent")


class TestJuiceShopScoreboard:
    def setup_method(self):
        self.profile = get_profile("juice_shop_scoreboard")

    def test_name(self):
        assert self.profile.name == "juice_shop_scoreboard"

    def test_target(self):
        assert self.profile.target == "juiceshop.cocode.dk"

    def test_objective_mentions_scoreboard(self):
        assert "scoreboard" in self.profile.objective.lower()

    def test_success_category(self):
        assert self.profile.success_category == "security_misconfiguration"

    def test_phases(self):
        assert self.profile.phases == ["recon", "enumerate", "report"]

    def test_mission_budget_has_required_keys(self):
        budget = self.profile.mission_budget
        for key in (
            "max_turns",
            "max_runtime_seconds",
            "max_llm_calls",
            "max_http_requests",
            "max_browser_actions",
            "max_asset_inspections",
        ):
            assert key in budget, f"Missing budget key: {key}"

    def test_mission_budget_values_positive(self):
        for key, value in self.profile.mission_budget.items():
            assert value > 0, f"{key}={value} should be positive"

    def test_mission_budget_turns(self):
        assert self.profile.mission_budget["max_turns"] == 25

    def test_mission_budget_runtime(self):
        assert self.profile.mission_budget["max_runtime_seconds"] == 300

    def test_mission_budget_llm_calls(self):
        assert self.profile.mission_budget["max_llm_calls"] == 30

    def test_mission_budget_http_requests(self):
        assert self.profile.mission_budget["max_http_requests"] == 60

    def test_mission_budget_browser_actions(self):
        assert self.profile.mission_budget["max_browser_actions"] == 40

    def test_mission_budget_asset_inspections(self):
        assert self.profile.mission_budget["max_asset_inspections"] == 10

    def test_phase_budgets_for_all_phases(self):
        for phase in self.profile.phases:
            assert phase in self.profile.phase_budgets, f"Missing phase budget: {phase}"

    def test_phase_budget_keys_are_valid(self):
        for phase, budget in self.profile.phase_budgets.items():
            assert isinstance(budget, dict)
            for key in budget:
                assert key.startswith("max_"), f"{key} should start with max_"

    def test_model_policy_is_dict(self):
        assert isinstance(self.profile.model_policy, dict)


class TestResolveModelPolicy:
    def test_uses_settings_defaults_when_profile_empty(self, settings):
        settings.AGENT_LLM_PROVIDER = "openrouter"
        settings.AGENT_LLM_MODEL = "deepseek/deepseek-v4-pro"
        settings.AGENT_LLM_REASONING_EFFORT = "high"
        profile = get_profile("juice_shop_scoreboard")
        result = resolve_model_policy(profile)
        assert result == {
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4-pro",
            "reasoning": {"effort": "high"},
        }

    def test_profile_overrides_settings(self, settings):
        settings.AGENT_LLM_PROVIDER = "openrouter"
        settings.AGENT_LLM_MODEL = "deepseek/deepseek-v4-pro"
        settings.AGENT_LLM_REASONING_EFFORT = "high"
        profile = MissionProfile(
            name="custom", target="t", objective="o",
            success_category="c", phases=["recon"],
            mission_budget={}, phase_budgets={},
            model_policy={"provider": "anthropic", "model": "claude-sonnet-4-5"},
        )
        result = resolve_model_policy(profile)
        assert result["provider"] == "anthropic"
        assert result["model"] == "claude-sonnet-4-5"

    def test_overrides_win_over_everything(self, settings):
        settings.AGENT_LLM_PROVIDER = "openrouter"
        settings.AGENT_LLM_MODEL = "deepseek/deepseek-v4-pro"
        settings.AGENT_LLM_REASONING_EFFORT = "high"
        profile = get_profile("juice_shop_scoreboard")
        result = resolve_model_policy(profile, overrides={
            "provider": "mock",
            "model": "test-model",
            "reasoning_effort": "low",
        })
        assert result == {
            "provider": "mock",
            "model": "test-model",
            "reasoning": {"effort": "low"},
        }


class TestProfilesDict:
    def test_profiles_is_dict(self):
        assert isinstance(_PROFILES, dict)

    def test_profiles_not_empty(self):
        assert len(_PROFILES) > 0

    def test_all_values_are_mission_profiles(self):
        for name, profile in _PROFILES.items():
            assert isinstance(profile, MissionProfile), f"{name} is not a MissionProfile"

    def test_profile_name_matches_key(self):
        for key, profile in _PROFILES.items():
            assert profile.name == key
