---
tier: FAST
depends_on: []
files:
  creates: []
  modifies:
    - backend/apps/agent/mission_profiles.py
    - backend/apps/agent/tests/test_mission_profiles.py
  deletes: []
exports:
  - juice_shop_login profile
imports: []
allow_extra_files: true
---

### Task 6: Budget keys and mission profile update

**Files:**
- Modify: `backend/apps/agent/mission_profiles.py`
- Modify if present: `backend/apps/agent/budget.py`
- Modify: `backend/apps/agent/tests/test_mission_profiles.py`

- [ ] **Step 1: Write failing tests for new budget keys**

Add to `test_mission_profiles.py`:

```python
class TestJuiceShopLoginProfile:
    def setup_method(self):
        self.profile = get_profile("juice_shop_login")

    def test_name(self):
        assert self.profile.name == "juice_shop_login"

    def test_phases_include_verify(self):
        assert "verify" in self.profile.phases

    def test_mission_budget_has_form_keys(self):
        budget = self.profile.mission_budget
        assert "max_form_fills" in budget
        assert "max_form_submits" in budget

    def test_verify_phase_budget_exists(self):
        assert "verify" in self.profile.phase_budgets
        assert "max_turns" in self.profile.phase_budgets["verify"]

    def test_probe_and_verify_have_form_limits(self):
        assert self.profile.phase_budgets["probe"]["max_form_fills"] > 0
        assert self.profile.phase_budgets["probe"]["max_form_submits"] > 0
        assert self.profile.phase_budgets["verify"]["max_form_fills"] > 0
        assert self.profile.phase_budgets["verify"]["max_form_submits"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_mission_profiles.py::TestJuiceShopLoginProfile -v`
Expected: FAIL — `KeyError: 'juice_shop_login'`

- [ ] **Step 3: Add juice_shop_login profile**

If the budget implementation has an explicit counter registry or counter-to-limit mapping, add `form_fills -> max_form_fills` and `form_submits -> max_form_submits` there before adding the profile. Do not add a separate `verify_turns` counter; verify uses the existing per-phase `max_turns` budget under `phase_budgets["verify"]`.

Add to `_PROFILES` in `mission_profiles.py`:

```python
"juice_shop_login": MissionProfile(
    name="juice_shop_login",
    target="juiceshop.cocode.dk",
    objective=(
        "Discover login/registration forms on OWASP Juice Shop, "
        "attempt common credential combinations, and verify "
        "any authentication bypass or weak credential findings."
    ),
    success_category="broken_authentication",
    phases=["recon", "enumerate", "probe", "verify", "report"],
    mission_budget={
        "max_turns": 40,
        "max_runtime_seconds": 300,
        "max_llm_calls": 35,
        "max_http_requests": 60,
        "max_browser_actions": 50,
        "max_asset_inspections": 10,
        "max_form_fills": 50,
        "max_form_submits": 20,
    },
    phase_budgets={
        "recon": {
            "max_turns": 6,
            "max_browser_actions": 10,
        },
        "enumerate": {
            "max_turns": 10,
            "max_browser_actions": 20,
            "max_form_fills": 15,
        },
        "probe": {
            "max_turns": 12,
            "max_browser_actions": 20,
            "max_form_fills": 25,
            "max_form_submits": 15,
        },
        "verify": {
            "max_turns": 8,
            "max_browser_actions": 10,
            "max_form_fills": 10,
            "max_form_submits": 5,
        },
        "report": {
            "max_turns": 4,
        },
    },
    model_policy={},
),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_mission_profiles.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/mission_profiles.py backend/apps/agent/tests/test_mission_profiles.py
git commit -m "feat(agent): add juice_shop_login profile with form budgets and verify phase"
```

If `backend/apps/agent/budget.py` was modified, include it in the `git add` command before committing.
