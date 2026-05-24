# Task 7: Integration — Full Probe Flow

**Files:**
- Modify: `backend/apps/agent/tests/test_integration.py`

---

- [ ] **Step 1: Write integration test for probe flow**

Add to `backend/apps/agent/tests/test_integration.py`:

```python
@pytest.mark.django_db
class TestProbeMissionFlow:
    """End-to-end: recon → enumerate → probe → report with click + http_request."""

    @pytest.mark.asyncio
    async def test_scoreboard_with_probe(self, db_objects):
        """Agent discovers scoreboard, probes it, submits candidate with evidence."""
        responses = [
            # recon: observe page
            _action_json(action="observe_page"),
            # recon → enumerate transition
            _action_json(
                action="request_phase_transition",
                from_phase="recon", to_phase="enumerate",
                reason="found JS bundles", evidence_refs=[],
            ),
            # enumerate: navigate to scoreboard
            _action_json(action="navigate", path="/#!/score-board"),
            # enumerate → probe transition
            _action_json(
                action="request_phase_transition",
                from_phase="enumerate", to_phase="probe",
                reason="found scoreboard", evidence_refs=[],
            ),
            # probe: click an element
            _action_json(action="click", element_id="link_0"),
            # probe: http_request
            _action_json(
                action="http_request", method="GET",
                path="/api/Challenges",
            ),
            # probe: submit candidate with evidence
            _action_json(
                action="submit_candidate",
                category="hidden_route_discovered",
                description="Scoreboard accessible without auth",
                evidence_refs=["obs_1", "obs_2"],
            ),
            # probe → report
            _action_json(
                action="request_phase_transition",
                from_phase="probe", to_phase="report",
                reason="evidence collected", evidence_refs=[],
            ),
            # report: stop
            _action_json(action="stop", reason="mission complete"),
        ]

        ctrl = _ctrl(
            db_objects, responses=responses,
            budget={"max_turns": 20},
        )
        ctrl._mission_phases = [
            "recon", "enumerate", "probe", "report",
        ]
        # Register a fake element for the click action
        ctrl.driver.click = AsyncMock()
        ctrl.driver.http_request = AsyncMock(return_value={
            "url": "https://test.example.com/api/Challenges",
            "method": "GET", "status": 200,
            "content_type": "application/json",
            "redirected": False,
            "final_url": "https://test.example.com/api/Challenges",
            "body_excerpt": '{"data": []}',
            "body_truncated": False,
            "trust": "untrusted_target_content",
        })

        await ctrl.run()

        ctrl.session.refresh_from_db()
        assert ctrl.session.status == "completed"

        from apps.agent.models import AgentObservation
        http_obs = AgentObservation.objects.filter(
            observation_type="http",
        ).count()
        assert http_obs >= 1

        ctrl.driver.click.assert_awaited_once()
        ctrl.driver.http_request.assert_awaited_once_with(
            "GET", "/api/Challenges",
        )
```

- [ ] **Step 2: Run integration test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_integration.py::TestProbeMissionFlow -v`
Expected: PASS

- [ ] **Step 3: Run full agent test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/ --tb=short -q`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/apps/agent/tests/test_integration.py
git commit -m "test(agent): add probe flow integration test"
```
