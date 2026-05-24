---
tier: FAST
depends_on: [04-viewset-read-list-detail]
files:
  creates: []
  modifies: [backend/config/urls.py]
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 9: URL Registration

**Files:**
- Modify: `backend/config/urls.py`

This step is already done in Task 4, Step 4 (the viewset was registered
to unblock tests). This task verifies it's correct and clean.

---

- [ ] **Step 1: Verify URL registration is present**

Check that `backend/config/urls.py` contains:

```python
from apps.agent.views import AgentSessionViewSet

router.register(r"agent/sessions", AgentSessionViewSet, basename="agent-session")
```

- [ ] **Step 2: Run a quick sanity test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && DJANGO_SETTINGS_MODULE=config.settings python -c "import django; django.setup(); from django.urls import reverse; print(reverse('agent-session-list'))"`

Expected output: `/api/agent/sessions/`

- [ ] **Step 3: Verify all routes resolve**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py -v`
Expected: ALL PASS — already passing from Task 4

- [ ] **Step 4: No commit needed — registration was committed in Task 4**
