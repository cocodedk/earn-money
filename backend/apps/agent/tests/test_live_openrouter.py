"""Live test that makes a real OpenRouter API call.

Run manually: LIVE_TESTS=1 python -m pytest apps/agent/tests/test_live_openrouter.py -v

Requires OPENROUTER_API_KEY in the environment.
"""
from __future__ import annotations

import asyncio
import json
import os

import pytest

LIVE = os.environ.get("LIVE_TESTS") == "1"
SKIP_REASON = "LIVE_TESTS=1 required for OpenRouter API calls"


def run(coro):
    return asyncio.run(coro)


@pytest.mark.skipunless(LIVE, reason=SKIP_REASON)
class TestLiveOpenRouter:
    def test_returns_valid_json_action(self):
        from apps.agent.llm.providers import OpenRouterProvider

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        assert api_key, "OPENROUTER_API_KEY must be set"

        provider = OpenRouterProvider(
            model="deepseek/deepseek-v4-pro",
            api_key=api_key,
            extra_params={"reasoning": {"effort": "high"}},
        )

        system = (
            "You are a security testing agent. "
            "Respond with a single raw JSON object. "
            "No markdown, no code fences, no prose.\n"
            '{"action": "observe_page", "goal": "...", '
            '"reason": "...", "hypothesis": "..."}'
        )
        messages = [
            {"role": "user", "content": "What do you see on the page?"},
        ]

        resp = run(provider.complete(system, messages))

        assert resp.raw_text, "Response should not be empty"
        assert resp.input_tokens > 0
        assert resp.output_tokens > 0

        parsed = json.loads(resp.raw_text)
        assert isinstance(parsed, dict), "Response must be a JSON object"
        assert "action" in parsed, "Response must have an 'action' field"
        assert not resp.raw_text.strip().startswith("```"), (
            "Response must not be wrapped in markdown code fences"
        )
