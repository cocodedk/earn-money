from __future__ import annotations

import pytest
from datetime import timedelta
from django.utils import timezone

from apps.agent.target_intel import (
    FormSignature, PriorCandidate, TargetIntel,
    build_target_intel, format_intel_prompt,
)


@pytest.fixture
def target_with_session(db):
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.targets.models import ScanTarget
    from apps.agent.persistence import create_session
    from apps.agent.models import SessionStatus

    project = Project.objects.create(name="intel-test")
    target = ScanTarget.objects.create(host="test.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    session.status = SessionStatus.COMPLETED
    session.finished_at = timezone.now()
    session.save(update_fields=["status", "finished_at"])
    return {"target": target, "session": session, "scan_run": scan_run}


@pytest.fixture
def old_session_for_same_target(target_with_session):
    from apps.agent.persistence import create_session
    from apps.agent.models import SessionStatus
    from apps.scans.models import ScanRun, ScanTargetRun
    target = target_with_session["target"]
    scan_run = ScanRun.objects.create(project=target.project, stub_slug="agent.v3.old")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    older = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    older.status = SessionStatus.COMPLETED
    older.finished_at = timezone.now() - timedelta(days=1)
    older.save(update_fields=["status", "finished_at"])
    return older


class TestBuildTargetIntelNoSession:
    @pytest.mark.django_db
    def test_returns_none_without_prior_session(self, db):
        from apps.projects.models import Project
        from apps.targets.models import ScanTarget

        project = Project.objects.create(name="no-session")
        target = ScanTarget.objects.create(host="fresh.example.com", project=project)
        result = build_target_intel(target, stale_after_days=7)
        assert result is None


@pytest.mark.django_db
class TestBuildTargetIntelWithSession:
    def test_returns_target_intel(self, target_with_session):
        target = target_with_session["target"]
        intel = build_target_intel(target, stale_after_days=7)
        assert isinstance(intel, TargetIntel)
        assert intel.source_session_id == str(target_with_session["session"].pk)

    def test_fresh_session_not_stale(self, target_with_session):
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert intel.is_stale is False

    def test_old_session_is_stale(self, target_with_session):
        session = target_with_session["session"]
        session.finished_at = timezone.now() - timedelta(days=10)
        session.save(update_fields=["finished_at"])
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert intel.is_stale is True

    def test_excludes_current_session(self, target_with_session, old_session_for_same_target):
        intel = build_target_intel(
            target_with_session["target"],
            exclude_session_id=target_with_session["session"].pk,
            stale_after_days=7,
        )
        assert intel.source_session_id == str(old_session_for_same_target.pk)


@pytest.mark.django_db
class TestBuildTargetIntelRoutesAndForms:
    def test_extracts_routes_from_notes(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "route", {"path": "/#!/score-board"})
        record_note(session, turn, "route", {"path": "/api/Challenges"})

        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert "/#!/score-board" in intel.known_routes
        assert "/api/Challenges" in intel.known_routes

    def test_hash_routes_preserved(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "route", {"path": "/#!/login"})

        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert "/#!/login" in intel.known_routes

    def test_max_routes_cap(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        for i in range(25):
            record_note(session, turn, "route", {"path": f"/route/{i}"})

        intel = build_target_intel(
            target_with_session["target"], stale_after_days=7, max_routes=10,
        )
        assert len(intel.known_routes) == 10

    def test_extracts_form_signatures(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "form", {
            "action": "/login", "method": "post",
            "input_names": ["email", "password"],
        })
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert intel.form_signatures[0].method == "POST"
        assert intel.form_signatures[0].input_names == ["email", "password"]


@pytest.mark.django_db
class TestBuildTargetIntelCandidates:
    def test_extracts_candidates(self, target_with_session):
        session = target_with_session["session"]
        from apps.agent.persistence import create_turn
        from apps.agent.models import AgentAction, ValidationStatus, ExecutionStatus
        turn = create_turn(session, model="mock")
        AgentAction.objects.create(
            turn=turn, action_type="submit_candidate",
            args_redacted={}, goal="found scoreboard",
            reason="r", hypothesis="h",
            validation_status=ValidationStatus.VALID,
            execution_status=ExecutionStatus.EXECUTED,
        )

        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        assert len(intel.prior_candidates) == 1
        assert intel.prior_candidates[0].description == "found scoreboard"


@pytest.mark.django_db
class TestFormatIntelPrompt:
    def test_returns_empty_for_none(self):
        assert format_intel_prompt(None) == ""

    def test_includes_source_session(self, target_with_session):
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        prompt = format_intel_prompt(intel)
        assert "Prior Target Intel" in prompt
        assert str(intel.source_session_id) in prompt

    def test_stale_label_present(self, target_with_session):
        session = target_with_session["session"]
        session.finished_at = timezone.now() - timedelta(days=10)
        session.save(update_fields=["finished_at"])
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        prompt = format_intel_prompt(intel)
        assert "stale" in prompt

    def test_fresh_label_present(self, target_with_session):
        intel = build_target_intel(target_with_session["target"], stale_after_days=7)
        prompt = format_intel_prompt(intel)
        assert "fresh" in prompt

    def test_deterministic_output(self, target_with_session):
        target = target_with_session["target"]
        a = format_intel_prompt(build_target_intel(target, stale_after_days=7))
        b = format_intel_prompt(build_target_intel(target, stale_after_days=7))
        assert a == b
