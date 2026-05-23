---
tier: CAPABLE
depends_on: []
files:
  creates: []
  modifies:
    - backend/apps/agent/event_log.py
    - backend/apps/agent/tests/test_event_log.py
  deletes: []
  renames: []
  generated: []
exports:
  - name: build_budget_snapshot
    file: backend/apps/agent/event_log.py
  - name: summarize_observation
    file: backend/apps/agent/event_log.py
imports: []
allow_extra_files: false
---

# Task 6A: Event Enrichment — Helpers

**Files:**
- Modify: `backend/apps/agent/event_log.py`
- Modify: `backend/apps/agent/tests/test_event_log.py`

---

- [ ] **Step 1: Write test for build_budget_snapshot helper**

Add to `backend/apps/agent/tests/test_event_log.py`:

```python
import pytest
from apps.agent.event_log import build_budget_snapshot


@pytest.mark.django_db
class TestBuildBudgetSnapshot:
    def test_returns_phase_consumed_and_mission_budget(self, create_session):
        session = create_session(
            mission_budget={"max_turns": 25, "max_http_requests": 60},
        )
        session.current_phase = "enumerate"
        consumed = {"mission": {"turns": 4}, "phase": {"turns": 2}}
        result = build_budget_snapshot(session, consumed)
        assert result == {
            "phase": "enumerate",
            "consumed": consumed,
            "mission_budget": {"max_turns": 25, "max_http_requests": 60},
        }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py::TestBuildBudgetSnapshot -v`
Expected: FAIL — `ImportError: cannot import name 'build_budget_snapshot'`

- [ ] **Step 3: Write build_budget_snapshot**

Add to `backend/apps/agent/event_log.py`:

```python
def build_budget_snapshot(session: AgentSession, consumed: dict) -> dict:
    return {
        "phase": session.current_phase,
        "consumed": consumed,
        "mission_budget": session.mission_budget,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py::TestBuildBudgetSnapshot -v`
Expected: PASS

- [ ] **Step 5: Write test for summarize_observation**

Add to `test_event_log.py`:

```python
from apps.agent.event_log import summarize_observation


class TestSummarizeObservation:
    def test_extracts_compact_summary(self):
        obs = {
            "url": "https://juiceshop.cocode.dk/",
            "title": "OWASP Juice Shop",
            "discovered": {
                "routes": ["/", "/rest/products"],
                "assets": ["/main.js"],
            },
            "elements": {
                "links": [{"href": "/"}],
                "buttons": [{"text": "Login"}, {"text": "Search"}],
                "forms": [{"action": "/rest/user/login"}],
            },
            "network": [{"url": "/rest/products"}, {"url": "/api/Challenges"}],
        }
        result = summarize_observation(obs)
        assert result == {
            "url": "https://juiceshop.cocode.dk/",
            "title": "OWASP Juice Shop",
            "route_count": 2,
            "asset_count": 1,
            "element_count": 4,
            "network_count": 2,
        }

    def test_handles_empty_observation(self):
        result = summarize_observation({})
        assert result == {
            "url": "",
            "title": "",
            "route_count": 0,
            "asset_count": 0,
            "element_count": 0,
            "network_count": 0,
        }

    def test_handles_malformed_nested_values(self):
        result = summarize_observation({
            "discovered": None,
            "elements": {"links": None, "buttons": "bad", "forms": []},
            "network": None,
        })
        assert result["route_count"] == 0
        assert result["asset_count"] == 0
        assert result["element_count"] == 0
        assert result["network_count"] == 0
```

- [ ] **Step 6: Write summarize_observation**

Add to `backend/apps/agent/event_log.py`:

```python
def summarize_observation(obs_dict: dict) -> dict:
    obs_dict = obs_dict or {}
    if not isinstance(obs_dict, dict):
        obs_dict = {}
    discovered = obs_dict.get("discovered") or {}
    elements = obs_dict.get("elements") or {}
    if not isinstance(discovered, dict):
        discovered = {}
    if not isinstance(elements, dict):
        elements = {}

    def _list(value) -> list:
        return value if isinstance(value, list) else []

    return {
        "url": obs_dict.get("url", ""),
        "title": obs_dict.get("title", ""),
        "route_count": len(_list(discovered.get("routes"))),
        "asset_count": len(_list(discovered.get("assets"))),
        "element_count": (
            len(_list(elements.get("links")))
            + len(_list(elements.get("buttons")))
            + len(_list(elements.get("forms")))
        ),
        "network_count": len(_list(obs_dict.get("network"))),
    }
```

- [ ] **Step 7: Run summarize test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_event_log.py::TestSummarizeObservation -v`
Expected: PASS

Continues in [06-event-enrichment-emitters.md](06-event-enrichment-emitters.md).
