"""Tests for stub 2.22 tenant-org-join-abuse classifier."""
from __future__ import annotations

from unittest.mock import MagicMock

from apps.stubs.tenant_org_join_abuse.classify import (
    TenantJoinFlawKind,
    classify_join_success,
    classify_join_surface,
    classify_rejected_join,
)


def _resp(status: int, body: str, method: str = "GET") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.request = MagicMock()
    r.request.method = method
    return r


class TestClassifyJoinSurface:
    def test_workspace_path_with_join_body_is_candidate(self):
        r = _resp(200, '{"join_url":"/api/workspaces/acme/join","workspace":"acme"}')
        result = classify_join_surface(r, "http://x.test/workspace/acme")
        assert result is not None
        assert result.kind == TenantJoinFlawKind.UNAUTHORIZED_JOIN
        assert result.status == "candidate"
        assert result.confidence == "low"

    def test_no_join_signal_in_body_is_none(self):
        r = _resp(200, '{"dashboard":true}')
        result = classify_join_surface(r, "http://x.test/workspace/acme")
        assert result is None

    def test_non_200_is_none(self):
        r = _resp(404, "Not found")
        result = classify_join_surface(r, "http://x.test/workspace/acme")
        assert result is None

    def test_non_workspace_path_is_none(self):
        r = _resp(200, '{"join_url":"/join"}')
        result = classify_join_surface(r, "http://x.test/api/users")
        assert result is None


class TestClassifyJoinSuccess:
    def test_vulnerable_marker_is_confirmed(self):
        r = _resp(200, '{"TENANT_ORG_JOIN_ABUSE_VULNERABLE":true,"workspace_member":true}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is not None
        assert result.kind == TenantJoinFlawKind.UNAUTHORIZED_JOIN
        assert result.confidence == "high"
        assert result.status == "confirmed"

    def test_joined_existing_tenant_marker_is_confirmed(self):
        r = _resp(200, '{"TENANT_ORG_JOIN_ABUSE_JOINED_EXISTING_TENANT":true}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is not None
        assert result.status == "confirmed"

    def test_workspace_member_true_is_confirmed(self):
        r = _resp(200, '{"workspace_member":true,"workspace":"acme"}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is not None

    def test_403_is_none(self):
        r = _resp(403, '{"TENANT_ORG_JOIN_ABUSE_INVITE_REQUIRED":true}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is None

    def test_401_is_none(self):
        r = _resp(401, '{"error":"unauthenticated"}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is None

    def test_separate_tenant_marker_is_none(self):
        r = _resp(200, '{"TENANT_ORG_JOIN_ABUSE_SEPARATE_TENANT_CREATED":true}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is None

    def test_pending_approval_marker_is_none(self):
        r = _resp(200, '{"TENANT_ORG_JOIN_ABUSE_PENDING_APPROVAL":true}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is None

    def test_invite_required_marker_is_none(self):
        r = _resp(200, '{"TENANT_ORG_JOIN_ABUSE_INVITE_REQUIRED":true}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is None

    def test_200_without_success_markers_is_none(self):
        r = _resp(200, '{"status":"ok"}', method="POST")
        result = classify_join_success(r, "http://x.test/api/workspaces/acme/join", tenant_id="acme")
        assert result is None


class TestClassifyRejectedJoin:
    def test_invite_required_marker_is_rejected(self):
        r = _resp(403, '{"TENANT_ORG_JOIN_ABUSE_INVITE_REQUIRED":true}', method="POST")
        result = classify_rejected_join(r, "http://x.test/api/workspaces/acme/join-secure")
        assert result is not None
        assert result.kind == TenantJoinFlawKind.INVITE_REQUIRED
        assert result.status == "rejected"
        assert result.confidence == "high"

    def test_403_without_marker_is_rejected(self):
        r = _resp(403, '{"error":"forbidden"}', method="POST")
        result = classify_rejected_join(r, "http://x.test/api/workspaces/acme/join-secure")
        assert result is not None
        assert result.status == "rejected"

    def test_separate_tenant_created_is_rejected(self):
        r = _resp(200, '{"TENANT_ORG_JOIN_ABUSE_SEPARATE_TENANT_CREATED":true}', method="POST")
        result = classify_rejected_join(r, "http://x.test/api/workspaces/acme/join")
        assert result is not None
        assert result.kind == TenantJoinFlawKind.SEPARATE_TENANT_CREATED
        assert result.status == "rejected"

    def test_200_without_rejection_markers_is_none(self):
        r = _resp(200, '{"workspace_member":true}', method="POST")
        result = classify_rejected_join(r, "http://x.test/api/workspaces/acme/join")
        assert result is None

    def test_non_standard_status_is_none(self):
        r = _resp(404, '{"error":"not_found"}', method="POST")
        result = classify_rejected_join(r, "http://x.test/api/workspaces/acme/join")
        assert result is None
