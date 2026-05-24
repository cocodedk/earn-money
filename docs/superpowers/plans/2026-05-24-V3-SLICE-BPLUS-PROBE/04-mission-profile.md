# Task 4: Mission Profile — Add Probe Phase + Budgets

**Files:**
- Modify: `backend/apps/agent/mission_profiles.py`
- Modify: `backend/apps/agent/tests/test_mission_profiles.py`

---

- [ ] **Step 1: Write test for probe phase in profile**

Add to `backend/apps/agent/tests/test_mission_profiles.py`:

```python
class TestJuiceShopScoreboardProbe:
    def setup_method(self):
        self.profile = get_profile("juice_shop_scoreboard")

    def test_phases_include_probe(self):
        assert self.profile.phases == [
            "recon", "enumerate", "probe", "report",
        ]

    def test_probe_budget_exists(self):
        assert "probe" in self.profile.phase_budgets

    def test_probe_budget_has_turns(self):
        assert self.profile.phase_budgets["probe"]["max_turns"] > 0

    def test_probe_budget_has_http_requests(self):
        assert self.profile.phase_budgets["probe"]["max_http_requests"] > 0
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_mission_profiles.py::TestJuiceShopScoreboardProbe -v`

- [ ] **Step 3: Update mission profile**

In `backend/apps/agent/mission_profiles.py`, change:

```python
        phases=["recon", "enumerate", "probe", "report"],
```

Add probe budget:

```python
        phase_budgets={
            "recon": {
                "max_turns": 8,
                "max_browser_actions": 15,
                "max_http_requests": 20,
            },
            "enumerate": {
                "max_turns": 12,
                "max_browser_actions": 20,
                "max_http_requests": 30,
            },
            "probe": {
                "max_turns": 10,
                "max_browser_actions": 15,
                "max_http_requests": 20,
            },
            "report": {
                "max_turns": 5,
                "max_browser_actions": 5,
                "max_http_requests": 10,
            },
        },
```

Also update `max_turns` in mission_budget from 25 to 35 to accommodate probe.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Fix existing test that asserts phases == 3**

Update `TestJuiceShopScoreboard.test_phases` to expect the new 4-phase list. Update `test_mission_budget_turns` to expect 35.

- [ ] **Step 6: Run full profile tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_mission_profiles.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/apps/agent/mission_profiles.py backend/apps/agent/tests/test_mission_profiles.py
git commit -m "feat(agent): add probe phase + budgets to scoreboard profile"
```
