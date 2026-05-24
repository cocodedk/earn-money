"""Coverage tests for _target_intel_extractors edge cases."""
from __future__ import annotations

import pytest
from django.utils import timezone

from apps.agent.target_intel import build_target_intel, format_intel_prompt


@pytest.fixture
def session_fixture(db):
    from apps.projects.models import Project
    from apps.scans.models import ScanRun, ScanTargetRun
    from apps.targets.models import ScanTarget
    from apps.agent.persistence import create_session
    from apps.agent.models import SessionStatus

    project = Project.objects.create(name="extractor-test")
    target = ScanTarget.objects.create(host="ext.example.com", project=project)
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.ext")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)
    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile="test", model_policy={}, mission_budget={},
    )
    session.status = SessionStatus.COMPLETED
    session.finished_at = timezone.now()
    session.save(update_fields=["status", "finished_at"])
    return {"target": target, "session": session}


@pytest.mark.django_db
class TestExtractRoutesEdgeCases:
    def test_non_dict_route_content_skipped(self, session_fixture):
        """Route notes with non-dict content are silently skipped."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        from apps.agent.models import AgentNote, NoteType
        turn = create_turn(session, model="mock")
        # Directly create note with non-dict content (string)
        AgentNote.objects.create(
            session=session, turn=turn, note_type="route", content={"raw": "not-a-path"},
        )
        record_note(session, turn, "route", {"path": "/real-route"})
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert "/real-route" in intel.known_routes

    def test_empty_path_skipped(self, session_fixture):
        """Route notes with empty path string don't get added to routes set."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "route", {"path": ""})
        record_note(session, turn, "route", {"path": "/good-route"})
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert "" not in intel.known_routes
        assert "/good-route" in intel.known_routes


@pytest.mark.django_db
class TestExtractFormSignaturesEdgeCases:
    def test_non_dict_form_note_skipped(self, session_fixture):
        """Form notes with non-dict content are skipped."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn
        from apps.agent.models import AgentNote
        turn = create_turn(session, model="mock")
        AgentNote.objects.create(
            session=session, turn=turn, note_type="form", content="bad",
        )
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert intel.form_signatures == []

    def test_non_list_input_names_treated_as_empty(self, session_fixture):
        """input_names that isn't a list is replaced with []."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "form", {
            "action": "/search", "method": "get", "input_names": "q",
        })
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert intel.form_signatures[0].input_names == []

    def test_dict_style_input_names_extracted(self, session_fixture):
        """input_names as list of dicts — extracts the 'name' key."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "form", {
            "action": "/contact", "method": "post",
            "input_names": [{"name": "email"}, {"name": "message"}],
        })
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert intel.form_signatures[0].input_names == ["email", "message"]

    def test_duplicate_form_deduped(self, session_fixture):
        """Identical form signatures are recorded only once."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "form", {
            "action": "/login", "method": "post", "input_names": ["user", "pass"],
        })
        record_note(session, turn, "form", {
            "action": "/login", "method": "post", "input_names": ["user", "pass"],
        })
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert len(intel.form_signatures) == 1

    def test_max_forms_cap(self, session_fixture):
        """Form signatures are capped at max_forms."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        for i in range(15):
            record_note(session, turn, "form", {
                "action": f"/form/{i}", "method": "post", "input_names": [],
            })
        intel = build_target_intel(
            session_fixture["target"], stale_after_days=7, max_forms=5,
        )
        assert len(intel.form_signatures) == 5

    def test_no_action_form_skipped(self, session_fixture):
        """Form note with empty action is skipped."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "form", {
            "action": "", "method": "post", "input_names": ["q"],
        })
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert intel.form_signatures == []


@pytest.mark.django_db
class TestExtractHypothesesEdgeCases:
    def test_dict_hypothesis_with_text_field(self, session_fixture):
        """Hypothesis note with 'text' key is extracted."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "hypothesis", {"text": "SQL injection possible"})
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert "SQL injection possible" in intel.hypotheses

    def test_dict_hypothesis_with_description_field(self, session_fixture):
        """Hypothesis note with 'description' key is extracted when 'text' absent."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "gap", {"description": "Auth bypass gap"})
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert "Auth bypass gap" in intel.hypotheses

    def test_empty_hypothesis_skipped(self, session_fixture):
        """Hypothesis notes with empty text are not included."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn, record_note
        turn = create_turn(session, model="mock")
        record_note(session, turn, "hypothesis", {"text": ""})
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert intel.hypotheses == []

    def test_non_dict_hypothesis_content_coerced_to_string(self, session_fixture):
        """Hypothesis note with non-dict content is coerced via str()."""
        session = session_fixture["session"]
        from apps.agent.persistence import create_turn
        from apps.agent.models import AgentNote
        turn = create_turn(session, model="mock")
        # Store a string directly as content (JSONField accepts any JSON value)
        AgentNote.objects.create(
            session=session, turn=turn, note_type="hypothesis",
            content="SSRF via redirector",
        )
        intel = build_target_intel(session_fixture["target"], stale_after_days=7)
        assert "SSRF via redirector" in intel.hypotheses
