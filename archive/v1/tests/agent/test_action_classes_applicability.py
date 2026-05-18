"""Tests for action classification + applicability scaffolding (applicability)."""
from __future__ import annotations

from earn_money.agent.action_classes import ActionClass, untried_applicable_classes
from earn_money.agent.hacker_session import HackerSession

from ._action_classes_helpers import _obs, _profile

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
