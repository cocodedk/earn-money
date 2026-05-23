### Task 18: Mission profiles

**Files:**
- Create: `backend/apps/agent/mission_profiles.py`
- Create: `backend/apps/agent/tests/test_mission_profiles.py`

- [ ] **Step 1: Write tests**

```python
# backend/apps/agent/tests/test_mission_profiles.py
import pytest
from apps.agent.mission_profiles import get_profile, MissionProfile


def test_juice_shop_scoreboard_profile():
    profile = get_profile("juice_shop_scoreboard")
    assert profile.objective == "Find the hidden admin scoreboard page"
    assert profile.phases == ["recon", "enumerate", "report"]
    assert profile.mission_budget["max_turns"] == 25
    assert "recon" in profile.phase_budgets


def test_unknown_profile_raises():
    with pytest.raises(KeyError):
        get_profile("nonexistent_profile")


def test_profile_has_all_budget_dimensions():
    profile = get_profile("juice_shop_scoreboard")
    for dim in ("max_turns", "max_http_requests", "max_asset_inspections"):
        assert dim in profile.mission_budget


def test_profile_declares_model_policy():
    profile = get_profile("juice_shop_scoreboard")
    assert profile.model_policy["provider_type"] == "anthropic"
    assert profile.model_policy["primary_model"] == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_mission_profiles.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# backend/apps/agent/mission_profiles.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MissionProfile:
    name: str
    target: str
    objective: str
    success_category: str
    phases: list[str]
    mission_budget: dict[str, int]
    phase_budgets: dict[str, dict[str, int]]
    model_policy: dict[str, Any] = field(default_factory=dict)


_PROFILES: dict[str, MissionProfile] = {
    "juice_shop_scoreboard": MissionProfile(
        name="juice_shop_scoreboard",
        target="juiceshop.cocode.dk",
        objective="Find the hidden admin scoreboard page",
        success_category="hidden_route_discovered",
        phases=["recon", "enumerate", "report"],
        mission_budget={
            "max_turns": 25,
            "max_runtime_seconds": 300,
            "max_llm_calls": 30,
            "max_http_requests": 60,
            "max_browser_actions": 40,
            "max_asset_inspections": 10,
        },
        phase_budgets={
            "recon": {
                "max_turns": 6,
                "max_http_requests": 20,
                "max_asset_inspections": 5,
            },
            "enumerate": {
                "max_turns": 14,
                "max_http_requests": 35,
                "max_asset_inspections": 5,
            },
            "report": {
                "max_turns": 3,
                "max_http_requests": 0,
                "max_asset_inspections": 0,
            },
        },
        model_policy={
            "provider_type": "anthropic",
            "primary_model": "claude-sonnet-4-6",
        },
    ),
}


def get_profile(name: str) -> MissionProfile:
    return _PROFILES[name]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_mission_profiles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/mission_profiles.py backend/apps/agent/tests/test_mission_profiles.py
git commit -m "feat(agent): add juice_shop_scoreboard mission profile"
```
