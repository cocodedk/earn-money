---
tier: APEX
depends_on: [08-celery-task-code]
files:
  creates: []
  modifies:
    - backend/apps/agent/tests/test_tasks.py
  deletes: []
  renames: []
  generated: []
exports: []
imports: []
allow_extra_files: false
---

# Task 8C: Celery Task — Stopped, Failed, Idempotent Tests

Continues from [08-celery-task-impl.md](08-celery-task-impl.md).

**Files:**
- Modify: `backend/apps/agent/tests/test_tasks.py`

---

- [ ] **Step 5: Write test for stopped path**

Add to `test_tasks.py`:

```python
@pytest.mark.django_db
class TestRunAgentSessionStopped:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_stopped_maps_to_stopped_status(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value
            ctrl_instance.run = AsyncMock()
            def side_effect():
                session.status = SessionStatus.STOPPED
                session.save(update_fields=["status"])
            ctrl_instance.run.side_effect = side_effect

            run_agent_session(str(session.id))

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.STOPPED
        assert scan_run.status == RunStatus.STOPPED
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STOPPED,
        ).exists()
        assert Event.objects.filter(
            type=EventType.SCAN_RUN_STOPPED_FINAL,
        ).exists()
```

- [ ] **Step 6: Run stopped test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestRunAgentSessionStopped -v`
Expected: PASS

- [ ] **Step 7: Write test for failure path**

```python
@pytest.mark.django_db
class TestRunAgentSessionFailure:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_failure_marks_all_failed_and_stops_driver(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        mock_provider.return_value = MagicMock()
        driver = MagicMock()
        driver.stop = AsyncMock()
        mock_driver.return_value = driver

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            ctrl_instance = MockCtrl.return_value
            ctrl_instance.run = AsyncMock(
                side_effect=RuntimeError("boom"),
            )

            with pytest.raises(RuntimeError, match="boom"):
                run_agent_session(str(session.id))

        session.refresh_from_db()
        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert session.status == SessionStatus.FAILED
        assert target_run.status == RunStatus.FAILED
        assert scan_run.status == RunStatus.FAILED
        driver.stop.assert_awaited_once()
        assert Event.objects.filter(
            type=EventType.SCAN_RUN_FAILED,
        ).exists()
```

- [ ] **Step 8: Run failure test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestRunAgentSessionFailure -v`
Expected: PASS

- [ ] **Step 9: Write test for idempotent finalization**

```python
@pytest.mark.django_db
class TestIdempotentFinalization:
    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_does_not_overwrite_terminal_target_run(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        target_run.status = RunStatus.DONE
        target_run.save(update_fields=["status"])
        scan_run.status = RunStatus.DONE
        scan_run.save(update_fields=["status"])

        started_before = Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STARTED,
        ).count()

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            run_agent_session(str(session.id))
            MockCtrl.assert_not_called()

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.DONE
        assert scan_run.status == RunStatus.DONE
        mock_provider.assert_not_called()
        mock_driver.assert_not_called()
        assert Event.objects.filter(
            type=EventType.SCAN_TARGET_RUN_STARTED,
        ).count() == started_before

    @patch("apps.agent.tasks._build_driver")
    @patch("apps.agent.tasks._build_provider")
    def test_finalizes_terminal_session_without_rerunning_controller(
        self, mock_provider, mock_driver,
    ):
        session, target_run, scan_run = _create_session_for_task()
        session.status = SessionStatus.COMPLETED
        session.save(update_fields=["status"])

        with patch("apps.agent.tasks.MissionController") as MockCtrl:
            run_agent_session(str(session.id))
            MockCtrl.assert_not_called()

        target_run.refresh_from_db()
        scan_run.refresh_from_db()
        assert target_run.status == RunStatus.DONE
        assert scan_run.status == RunStatus.DONE
        mock_provider.assert_not_called()
        mock_driver.assert_not_called()


@pytest.mark.django_db
class TestBuildDriver:
    @patch("apps.agent.browser.driver.PlaywrightDriver")
    def test_uses_target_base_url_when_present(self, MockDriver):
        session, _target_run, _scan_run = _create_session_for_task()
        from apps.agent.tasks import _build_driver

        _build_driver(session.target)

        MockDriver.assert_called_once_with(
            target_origin="https://juiceshop.cocode.dk",
        )
```

- [ ] **Step 10: Run idempotent test**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py::TestIdempotentFinalization -v`
Expected: PASS

- [ ] **Step 11: Run full task test suite**

Run: `cd /home/cocodedk/0-projects/earn-money-backend/backend && python -m pytest apps/agent/tests/test_tasks.py -v`
Expected: ALL PASS

- [ ] **Step 12: Commit**

```bash
git add backend/apps/agent/tasks.py backend/apps/agent/tests/test_tasks.py
git commit -m "feat(agent): add Celery task with ScanRun/ScanTargetRun lifecycle"
```
