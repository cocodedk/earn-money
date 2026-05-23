---
tier: FAST
depends_on:
  - 02-action-obs-note-models
files:
  creates: []
  modifies:
    - backend/config/settings.py
  generated:
    - backend/apps/agent/migrations/0001_initial.py
allow_extra_files: false
---

### Task 3: Migrations and app registration

**Files:**
- Modify: `backend/config/settings.py`
- Create: `backend/apps/agent/migrations/` (generated)

- [ ] **Step 1: Add app to INSTALLED_APPS**

In `backend/config/settings.py`, add `"apps.agent"` after `"apps.stubs"`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    "apps.stubs",
    "apps.agent",
]
```

- [ ] **Step 2: Generate and run migrations**

Run: `cd backend && python manage.py makemigrations agent && python manage.py migrate`
Expected: Migration created and applied successfully

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest apps/agent/tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add backend/config/settings.py backend/apps/agent/migrations/
git commit -m "feat(agent): register app and generate initial migration"
```
