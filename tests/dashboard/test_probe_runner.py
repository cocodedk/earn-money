"""Tests for ProbeRunner — metadata, task-routing, base-host augmentation.

Lifecycle / event-emission tests live in the sibling
test_probe_runner_lifecycle.py and test_probe_runner_events.py.
"""
from __future__ import annotations

from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.task_router import TaskType

from ._probe_runner_test_helpers import _grab_meta, _j, _runner_with_session


class TestMetadataApi:
    """`runner.metadata()` exposes the same payload that the SSE `meta`
    event carries, so the `/api/probe/current` endpoint can answer
    "what is currently running?" without re-parsing the history."""

    def test_metadata_returns_meta_event_payload(self, make_runner):
        runner = make_runner([])
        m = runner.metadata()
        assert m["run_id"] == runner.run_id()
        assert m["base_url"] == "https://target.example.com"
        assert m["target_kind"] == "local_lab"
        assert m["max_turns"] == 10

    def test_metadata_includes_is_running_false_before_start(self, make_runner):
        runner = make_runner([])
        m = runner.metadata()
        assert m["is_running"] is False


class TestRunMetadata:
    """The dashboard needs to display run config (base_url, target_kind,
    roe_path, max_turns, platform, program) so a page reload + replay
    shows the operator what's actually running. ProbeRunner emits a
    `meta` SSE event as the very first history entry at construction
    time — deterministically seq=1, replayed to every subscriber."""

    def test_meta_event_is_seq_1(self, make_runner):
        runner = make_runner([])
        snapshot = runner._history.snapshot_seqs()
        assert snapshot, "no events in history — meta was not emitted"
        assert snapshot[0] == 1

    def test_meta_event_carries_base_url_and_target_kind(self, make_runner):
        runner = make_runner([])
        meta = _grab_meta(runner)
        assert meta is not None
        assert meta["data"]["base_url"] == "https://target.example.com"
        assert meta["data"]["target_kind"] == "local_lab"

    def test_meta_event_carries_run_id_and_max_turns(self, make_runner):
        runner = make_runner([])
        meta = _grab_meta(runner)
        assert meta["data"]["run_id"] == runner.run_id()
        # max_turns is whatever the loaded profile says; the test RoE
        # fixture sets it to 10.
        assert meta["data"]["max_turns"] == 10

    def test_meta_event_carries_roe_profile_path(self, make_runner):
        runner = make_runner([])
        meta = _grab_meta(runner)
        assert meta["data"]["roe_profile"].endswith("test.yaml")


class TestPickTask:
    def test_no_observations_picks_agent_planning(self):
        r = _runner_with_session([])
        assert r._pick_task() == TaskType.AGENT_PLANNING

    def test_javascript_content_type_picks_coding_security(self):
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "application/javascript"}, "var x=1;",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.CODING_SECURITY

    def test_html_with_script_picks_coding_security(self):
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "text/html"}, "<html><script>1</script></html>",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.CODING_SECURITY

    def test_html_without_script_picks_agent_planning(self):
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "text/html"}, "<html><body>hi</body></html>",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.AGENT_PLANNING

    def test_json_content_type_picks_agent_planning(self):
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "application/json"}, "{}",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.AGENT_PLANNING

    def test_report_candidate_hint_picks_structured_extraction(self):
        r = _runner_with_session([])
        r._next_task_hint = TaskType.STRUCTURED_EXTRACTION
        assert r._pick_task() == TaskType.STRUCTURED_EXTRACTION

    def test_hint_is_consumed_after_one_use(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        # Simulate a ReportCandidateAction having just been processed.
        runner._next_task_hint = TaskType.STRUCTURED_EXTRACTION
        assert runner._pick_task() == TaskType.STRUCTURED_EXTRACTION
        # Trigger the _on_turn_complete branch that clears the hint.
        from earn_money.agent.probe_actions import StopAction
        runner._on_turn_complete(2, StopAction(tool="stop", category="stop"), "completed")
        assert runner._next_task_hint is None


class TestBaseHostAugmentation:
    def test_local_lab_without_roe_adds_base_host(self):
        from earn_money.agent.roe_profile import RoeProfile, RoeSourceType
        from earn_money.dashboard.probe_runner import _augment_with_base_host

        profile = RoeProfile.safe_default()
        assert profile.allowed_hosts == []
        augmented = _augment_with_base_host(profile, "https://target.example.com:8443/x")
        assert augmented.allowed_hosts == ["target.example.com"]
        # source_type/ref preserved from safe_default
        assert augmented.source_type == RoeSourceType.MANUAL

    def test_augmentation_is_noop_when_host_already_present(self):
        from earn_money.agent.roe_profile import RoeProfile, RoeSourceType
        from earn_money.dashboard.probe_runner import _augment_with_base_host

        profile = RoeProfile(
            name="p", source_type=RoeSourceType.MANUAL,
            allowed_hosts=["target.example.com"],
        )
        out = _augment_with_base_host(profile, "https://target.example.com/")
        assert out is profile  # short-circuit, no rebuild
