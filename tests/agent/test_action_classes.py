"""Tests for action classification + applicability scaffolding."""
from __future__ import annotations

from earn_money.agent.action_classes import (
    ActionClass,
    classify_action,
    untried_applicable_classes,
)
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.probe_actions import (
    GetAction,
    PostAction,
    ReportCandidateAction,
    SetHeaderAction,
    StopAction,
    StoreAction,
)
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType


def _profile(**overrides: object) -> RoeProfile:
    defaults: dict[str, object] = dict(
        name="t",
        source_type=RoeSourceType.MANUAL,
        allowed_hosts=["target.example.com"],
        max_requests=100,
        max_posts=20,
        max_turns=10,
        max_runtime_seconds=60,
        max_response_bytes=5000,
        delay_between_requests_ms=0,
        allow_get=True,
        allow_post=True,
        allow_idor_checks=True,
    )
    defaults.update(overrides)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


def _obs(status: int, url: str, ctype: str = "text/html", body: str = "ok") -> ObservationWrapper:
    return ObservationWrapper.from_response(status, url, {"Content-Type": ctype}, body)


def _get(path: str) -> GetAction:
    return GetAction.model_validate({"tool": "get", "category": "http_get", "args": {"path": path}})


def _post(path: str, json_body: dict | None = None) -> PostAction:
    return PostAction.model_validate({
        "tool": "post", "category": "http_post",
        "args": {"path": path, "json": json_body or {}},
    })


# ── classifier ────────────────────────────────────────────────────────


class TestClassifier:
    def test_root_get_is_discovery(self):
        assert classify_action(_get("/")) == ActionClass.DISCOVERY_GET

    def test_robots_get_is_discovery(self):
        assert classify_action(_get("/robots.txt")) == ActionClass.DISCOVERY_GET

    def test_api_get_is_enumeration(self):
        assert classify_action(_get("/api/Users")) == ActionClass.API_ENUMERATION

    def test_rest_get_is_enumeration(self):
        assert classify_action(_get("/rest/products/search")) == ActionClass.API_ENUMERATION

    def test_login_get_is_auth_discovery(self):
        assert classify_action(_get("/rest/user/login")) == ActionClass.AUTH_DISCOVERY

    def test_login_post_is_auth_discovery(self):
        assert classify_action(_post("/rest/user/login")) == ActionClass.AUTH_DISCOVERY

    def test_register_get_is_auth_discovery(self):
        assert classify_action(_get("/api/Users/register")) == ActionClass.AUTH_DISCOVERY

    def test_session_get_is_auth_discovery(self):
        assert classify_action(_get("/rest/session")) == ActionClass.AUTH_DISCOVERY

    def test_js_bundle_get_is_client_analysis(self):
        assert classify_action(_get("/main.js")) == ActionClass.CLIENT_ANALYSIS

    def test_mjs_bundle_get_is_client_analysis(self):
        assert classify_action(_get("/static/chunk.mjs")) == ActionClass.CLIENT_ANALYSIS

    def test_non_auth_post_is_post_probe(self):
        assert classify_action(_post("/api/Products")) == ActionClass.POST_PROBE

    def test_set_header_is_header_probe(self):
        action = SetHeaderAction.model_validate({
            "tool": "set_header", "category": "auth",
            "args": {"name": "Authorization", "value": "Bearer x"},
        })
        assert classify_action(action) == ActionClass.HEADER_PROBE

    def test_store_action_is_not_classified(self):
        action = StoreAction.model_validate({
            "tool": "store", "category": "store_memory",
            "args": {"kind": "token", "key": "k", "value": "v"},
        })
        assert classify_action(action) is None

    def test_report_candidate_is_not_classified(self):
        action = ReportCandidateAction.model_validate({
            "tool": "report_candidate", "category": "report_candidate",
            "args": {"signal_type": "idor", "target": "/x", "evidence": "y", "confidence": "low"},
        })
        assert classify_action(action) is None

    def test_stop_is_not_classified(self):
        assert classify_action(StopAction.model_validate({
            "tool": "stop", "category": "stop", "args": {"reason": "done"},
        })) is None

    def test_auth_keyword_takes_priority_over_api_path(self):
        # /api/Users/login is BOTH an api path and an auth path; auth wins.
        assert classify_action(_get("/api/Users/login")) == ActionClass.AUTH_DISCOVERY


# ── applicability ─────────────────────────────────────────────────────


class TestApplicability:
    def test_empty_session_discovery_and_auth_only(self):
        session = HackerSession()
        applicable = untried_applicable_classes(session, _profile(), tried=set())
        assert applicable == {ActionClass.DISCOVERY_GET, ActionClass.AUTH_DISCOVERY}

    def test_client_analysis_applicable_after_html_observed(self):
        session = HackerSession()
        session.add_observation(_obs(200, "https://target.example.com/", ctype="text/html"))
        applicable = untried_applicable_classes(session, _profile(), tried=set())
        assert ActionClass.CLIENT_ANALYSIS in applicable

    def test_client_analysis_applicable_after_js_observed(self):
        session = HackerSession()
        session.add_observation(
            _obs(200, "https://target.example.com/main.js", ctype="application/javascript"),
        )
        applicable = untried_applicable_classes(session, _profile(), tried=set())
        assert ActionClass.CLIENT_ANALYSIS in applicable

    def test_api_enumeration_applicable_after_api_observed(self):
        session = HackerSession()
        session.add_observation(_obs(200, "https://target.example.com/api/Products"))
        applicable = untried_applicable_classes(session, _profile(), tried=set())
        assert ActionClass.API_ENUMERATION in applicable

    def test_post_probe_not_applicable_until_endpoint_known(self):
        session = HackerSession()
        applicable = untried_applicable_classes(session, _profile(allow_post=True), tried=set())
        assert ActionClass.POST_PROBE not in applicable

    def test_post_probe_applicable_after_api_endpoint_seen(self):
        session = HackerSession()
        session.add_observation(_obs(200, "https://target.example.com/api/Products"))
        applicable = untried_applicable_classes(session, _profile(allow_post=True), tried=set())
        assert ActionClass.POST_PROBE in applicable

    def test_post_probe_blocked_by_roe(self):
        session = HackerSession()
        session.add_observation(_obs(200, "https://target.example.com/api/Products"))
        applicable = untried_applicable_classes(session, _profile(allow_post=False), tried=set())
        assert ActionClass.POST_PROBE not in applicable

    def test_header_probe_applicable_after_401(self):
        session = HackerSession()
        session.add_observation(_obs(401, "https://target.example.com/api/Users"))
        applicable = untried_applicable_classes(session, _profile(), tried=set())
        assert ActionClass.HEADER_PROBE in applicable

    def test_header_probe_applicable_after_403(self):
        session = HackerSession()
        session.add_observation(_obs(403, "https://target.example.com/api/Admin"))
        applicable = untried_applicable_classes(session, _profile(), tried=set())
        assert ActionClass.HEADER_PROBE in applicable

    def test_header_probe_not_applicable_without_auth_boundary(self):
        session = HackerSession()
        session.add_observation(_obs(200, "https://target.example.com/"))
        applicable = untried_applicable_classes(session, _profile(), tried=set())
        assert ActionClass.HEADER_PROBE not in applicable

    def test_tried_class_excluded(self):
        session = HackerSession()
        applicable = untried_applicable_classes(
            session, _profile(), tried={ActionClass.DISCOVERY_GET},
        )
        assert ActionClass.DISCOVERY_GET not in applicable
        assert ActionClass.AUTH_DISCOVERY in applicable

    def test_all_classes_tried_returns_empty(self):
        session = HackerSession()
        session.add_observation(
            _obs(401, "https://target.example.com/api/Users", ctype="text/html"),
        )
        all_classes = set(ActionClass)
        applicable = untried_applicable_classes(session, _profile(), tried=all_classes)
        assert applicable == set()
