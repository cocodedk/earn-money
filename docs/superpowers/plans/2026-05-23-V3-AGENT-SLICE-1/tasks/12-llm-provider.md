### Task 12: LLM provider interface

**Files:**
- Create: `backend/apps/agent/llm/__init__.py`
- Create: `backend/apps/agent/llm/providers.py`
- Create: `backend/apps/agent/tests/test_providers.py`

Slice 1 uses a single frontier model. The provider interface is a thin wrapper
around the Anthropic or OpenAI SDK. We test with a mock provider.

- [ ] **Step 1: Write tests for provider**

```python
# backend/apps/agent/tests/test_providers.py
import pytest
import json
from unittest.mock import AsyncMock, patch
from apps.agent.llm.providers import LLMProvider, LLMResponse, create_provider


def test_llm_response_dataclass():
    resp = LLMResponse(
        raw_text='{"action": "observe_page", "goal": "See", "args": {}}',
        input_tokens=100, output_tokens=50,
        model="claude-sonnet-4-6",
    )
    assert resp.input_tokens == 100
    parsed = json.loads(resp.raw_text)
    assert parsed["action"] == "observe_page"


def test_create_provider_returns_provider():
    provider = create_provider(
        model="claude-sonnet-4-6", api_key="test-key", provider_type="mock",
    )
    assert isinstance(provider, LLMProvider)


@pytest.mark.asyncio
async def test_mock_provider_returns_valid_json():
    provider = create_provider(
        model="mock", api_key="", provider_type="mock",
    )
    resp = await provider.complete(
        system_prompt="You are an agent.",
        messages=[{"role": "user", "content": "What do you see?"}],
    )
    parsed = json.loads(resp.raw_text)
    assert "action" in parsed


@pytest.mark.asyncio
async def test_provider_tracks_token_usage():
    provider = create_provider(
        model="mock", api_key="", provider_type="mock",
    )
    resp = await provider.complete(
        system_prompt="test", messages=[{"role": "user", "content": "hi"}],
    )
    assert resp.input_tokens >= 0
    assert resp.output_tokens >= 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_providers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement provider**

```python
# backend/apps/agent/llm/__init__.py
# (empty)
```

```python
# backend/apps/agent/llm/providers.py
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    raw_text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        ...


class MockProvider(LLMProvider):
    async def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        action = json.dumps({
            "action": "observe_page",
            "goal": "Initial page observation",
            "reason": "First turn, need to see the page",
            "args": {},
        })
        return LLMResponse(
            raw_text=action, input_tokens=100,
            output_tokens=50, model="mock",
        )


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._api_key = api_key

    async def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> LLMResponse:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        response = await client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        text = response.content[0].text
        return LLMResponse(
            raw_text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
        )


def create_provider(
    model: str,
    api_key: str,
    provider_type: str = "anthropic",
) -> LLMProvider:
    if provider_type == "mock":
        return MockProvider()
    if provider_type == "anthropic":
        return AnthropicProvider(model=model, api_key=api_key)
    raise ValueError(f"Unknown provider type: {provider_type!r}")
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_providers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/llm/ backend/apps/agent/tests/test_providers.py
git commit -m "feat(agent): add LLM provider interface with mock + Anthropic"
```
