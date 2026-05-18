"""Tests for action classification + applicability scaffolding (classifier)."""
from __future__ import annotations

from earn_money.agent.action_classes import ActionClass, classify_action
from earn_money.agent.probe_actions import (
    ReportCandidateAction,
    SetHeaderAction,
    StopAction,
    StoreAction,
)

from ._action_classes_helpers import _get, _post

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
