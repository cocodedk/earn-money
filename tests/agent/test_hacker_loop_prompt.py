"""Prompt-assembly + taxonomy-hygiene tests for HackerLoop._build_prompt."""
from earn_money.agent.hacker_loop import _SYSTEM_PROMPT

from ._test_hacker_loop_helpers import _j, _loop


class TestBuildPrompt:
    """Prompt hygiene: `_build_prompt()` returns ONLY the user portion
    (RoE + Session State + actions). The system framing rides the
    `system=` kwarg to `provider.complete()` and must NOT also appear
    at the top of the user message — see `02-sse-event-shape.md`."""

    def test_build_prompt_does_not_contain_system_framing(self):
        loop = _loop([_j(tool="stop", category="stop", args={})])
        prompt = loop._build_prompt()
        assert _SYSTEM_PROMPT not in prompt
        assert "You are assisting with authorized security testing." not in prompt

    def test_build_prompt_starts_with_roe_heading(self):
        loop = _loop([_j(tool="stop", category="stop", args={})])
        assert loop._build_prompt().startswith("=== Rules of Engagement ===")

    def test_provider_complete_still_receives_system_kwarg(self):
        loop = _loop([_j(tool="stop", category="stop", args={})])
        loop.run()
        assert loop.provider.complete.call_args.kwargs["system"] == _SYSTEM_PROMPT

    def test_full_tab_concatenation_has_no_duplicated_system(self):
        """Full tab in the dashboard renders `system + "\\n\\n" + prompt`.
        Locks the contract that the result contains the framing exactly once."""
        loop = _loop([_j(tool="stop", category="stop", args={})])
        seen: list[dict] = []
        loop._on_llm_response = (  # type: ignore[method-assign]
            lambda turn, raw, model_id, **kw: seen.append(kw)
        )
        loop.run()
        full = seen[0]["system"] + "\n\n" + seen[0]["prompt"]
        assert full.count("You are an authorized vulnerability scanning agent.") == 1


class TestPromptTaxonomyHygiene:
    """The prompt must not expose ActionClass enum values to the model.

    A2 bench 2026-05-17: both mistral-3.2 and deepseek-v4-pro returned
    `{"tool": "auth_discovery", ...}` after seeing the class names in
    the system prompt. The class taxonomy is an internal coverage ID;
    the only valid tool dispatch identifiers are the six listed in the
    "Available actions" block.
    """

    def test_no_raw_enum_values_leak_into_full_prompt(self):
        from earn_money.agent.action_classes import ActionClass
        loop = _loop([_j(tool="stop", category="stop", args={})], presolved=False)
        full = _SYSTEM_PROMPT + "\n\n" + loop._build_prompt()
        for cls in ActionClass:
            assert cls.value not in full, (
                f"Raw enum value {cls.value!r} leaked into the prompt — "
                "LLMs conflate this with tool names."
            )

    def test_tool_list_precedes_coverage_block(self):
        loop = _loop([_j(tool="stop", category="stop", args={})])
        prompt = loop._build_prompt()
        tools_idx = prompt.index("=== Available actions ===")
        coverage_idx = prompt.index("=== Coverage status ===")
        assert tools_idx < coverage_idx, (
            "Strict tool schema must appear before coverage hints "
            "so the model anchors on it before reading taxonomy."
        )

    def test_coverage_block_uses_plain_english_for_auth_boundary(self):
        """When AUTH_DISCOVERY is untried+applicable, the prompt should
        describe the technique in human language, never as 'auth_discovery'."""
        loop = _loop([_j(tool="stop", category="stop", args={})], presolved=False)
        prompt = loop._build_prompt()
        assert "authentication boundary" in prompt
        assert "auth_discovery" not in prompt

    def test_prompt_states_strict_valid_tool_values(self):
        loop = _loop([_j(tool="stop", category="stop", args={})])
        full = _SYSTEM_PROMPT + "\n\n" + loop._build_prompt()
        assert "get, post, set_header, store, report_candidate, stop" in full
