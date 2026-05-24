---
tier: CAPABLE
depends_on: []
files:
  creates:
    - backend/apps/agent/target_intel.py
    - backend/apps/agent/tests/test_target_intel.py
  modifies: []
  deletes: []
exports:
  - backend/apps/agent/target_intel.py
imports: []
allow_extra_files: false
---

### Task 1: TargetIntel dataclasses and build_target_intel()

**Files:**
- Create: `backend/apps/agent/target_intel.py`
- Create: `backend/apps/agent/tests/test_target_intel.py`

- [ ] **Step 1: Write failing tests for TargetIntel construction**

Create `backend/apps/agent/tests/test_target_intel.py`:

Use the complete test module in [01-target-intel-test-code.md](01-target-intel-test-code.md). It includes no-session behavior, stale/fresh labeling, current-session exclusion, deterministic route extraction, form signatures, valid candidate extraction, and prompt formatting.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_target_intel.py -v`

- [ ] **Step 3: Implement target_intel.py**

See [01-target-intel-implementation.md](01-target-intel-implementation.md) for the full implementation code. Keep extraction deterministic with `order_by("pk")`, sanitize every string before prompt insertion, and exclude the current session when the caller passes `exclude_session_id`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend python -m pytest apps/agent/tests/test_target_intel.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/target_intel.py backend/apps/agent/tests/test_target_intel.py
git commit -m "feat(agent): add TargetIntel dataclass and build_target_intel()"
```
