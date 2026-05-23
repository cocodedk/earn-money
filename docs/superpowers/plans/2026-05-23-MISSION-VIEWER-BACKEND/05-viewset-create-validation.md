---
tier: CAPABLE
depends_on:
  - 05-viewset-create-success
files:
  creates: []
  modifies:
    - backend/apps/agent/tests/test_views.py
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 5C: Create Validation Tests

Continues from [05-viewset-create-success.md](05-viewset-create-success.md).

**Files:**
- Modify: `backend/apps/agent/tests/test_views.py`

---

- [ ] **Step 6: Write validation tests**

Add to `test_views.py`:

```python
class AgentSessionCreateValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="test")
        self.target = ScanTarget.objects.create(
            host="test.example.com", project=self.project,
        )

    def test_unknown_target_returns_400(self):
        import uuid
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(uuid.uuid4()),
        }, format="json")
        assert resp.status_code == 400

    def test_unknown_profile_returns_400(self):
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(self.target.id),
            "mission_profile": "nonexistent",
        }, format="json")
        assert resp.status_code == 400

    def test_duplicate_active_session_returns_400(self):
        from apps.agent.models import (
            AgentSession, AutonomyMode, AgentPhase, SessionStatus,
        )
        run = ScanRun.objects.create(
            project=self.project, stub_slug="agent.v3",
        )
        tr = ScanTargetRun.objects.create(
            scan_run=run, target=self.target,
        )
        AgentSession.objects.create(
            scan_target_run=tr, scan_run=run, target=self.target,
            autonomy_mode=AutonomyMode.LAB_FREE_RUN,
            current_phase=AgentPhase.RECON,
            status=SessionStatus.RUNNING,
            mission_profile="test",
        )
        url = reverse("agent-session-list")
        resp = self.client.post(url, {
            "target": str(self.target.id),
        }, format="json")
        assert resp.status_code == 400
        assert "active" in str(resp.json()).lower()
```

- [ ] **Step 7: Run validation tests**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py::AgentSessionCreateValidationTests -v`
Expected: ALL PASS

- [ ] **Step 8: Run full view test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_views.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add backend/apps/agent/serializers.py backend/apps/agent/views.py backend/apps/agent/tests/test_views.py
git commit -m "feat(agent): add start-mission POST with validation + Celery enqueue"
```
