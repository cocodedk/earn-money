---
tier: FAST
depends_on: []
files:
  creates: []
  modifies: [backend/apps/events/types.py, backend/apps/events/test_types.py]
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 1: Add SCAN_RUN_FAILED Event Type

**Files:**
- Modify: `backend/apps/events/types.py`
- Test: `backend/apps/events/test_types.py`

---

- [ ] **Step 1: Write test asserting SCAN_RUN_FAILED exists**

Add to `backend/apps/events/test_types.py`:

```python
def test_scan_run_failed_event_type_exists():
    assert EventType.SCAN_RUN_FAILED == "scan_run.failed"
    assert EventType.SCAN_RUN_FAILED.label == "Scan run failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/events/test_types.py::test_scan_run_failed_event_type_exists -v`
Expected: FAIL — `AttributeError: SCAN_RUN_FAILED`

- [ ] **Step 3: Add SCAN_RUN_FAILED to EventType**

In `backend/apps/events/types.py`, add after the `SCAN_RUN_DONE` line:

```python
    SCAN_RUN_FAILED = "scan_run.failed", "Scan run failed"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/events/test_types.py::test_scan_run_failed_event_type_exists -v`
Expected: PASS

- [ ] **Step 5: Generate migration if Django detects the choice-list change**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python manage.py makemigrations events --check`

If it exits non-zero (changes detected), generate:
`python manage.py makemigrations events -n add_scan_run_failed_choice`

If it exits 0 (no changes), skip — Django sometimes does not require a
migration for `choices=` additions since the DB column type doesn't change.

- [ ] **Step 6: Commit**

```bash
git add backend/apps/events/types.py backend/apps/events/test_types.py backend/apps/events/migrations/
git commit -m "feat(events): add SCAN_RUN_FAILED event type"
```
