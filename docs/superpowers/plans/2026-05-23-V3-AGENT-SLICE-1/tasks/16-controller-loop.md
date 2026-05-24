---
tier: APEX
depends_on: [04-action-schemas, 05-phase-matrix, 06-budget-tracker, 07-plateau-detection, 10-observation-builder, 11-playwright-driver, 13-system-prompt, 14-persistence, 15-event-logging, 17-phase-transitions]
files:
  creates:
    - backend/apps/agent/controller.py
    - backend/apps/agent/tests/test_controller.py
  modifies: []
allow_extra_files: false
---

### Task 16: Controller loop

**Files:**
- Create: `backend/apps/agent/controller.py`
- Create: `backend/apps/agent/tests/test_controller.py`

The controller is the core mission loop. It orchestrates: LLM call → parse →
validate → execute → observe → persist → budget check → repeat.

**Prerequisite:** Task 17 must be complete before this task because the controller
imports phase transition helpers.

- [ ] **Step 1: Write tests** — see [16-controller-loop-tests.md](16-controller-loop-tests.md)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_controller.py -v`
Expected: FAIL

- [ ] **Step 3: Implement** — split across three files:
  - [16-controller-loop-impl.md](16-controller-loop-impl.md) — imports, `__init__`, `run()`
  - [16-controller-loop-turn.md](16-controller-loop-turn.md) — `_run_turn()`
  - [16-controller-loop-execute.md](16-controller-loop-execute.md) — `_execute_action()`

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_controller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/controller.py backend/apps/agent/tests/test_controller.py
git commit -m "feat(agent): add MissionController with phase/budget/plateau loop"
```
