"""Tests for stub 2.21 invitation-abuse classifier — mutation phase."""
from __future__ import annotations

from unittest.mock import MagicMock

from apps.stubs.invitation_abuse.classify import (
    InviteFlawKind,
    classify_reuse,
    classify_role_escalation,
    classify_wrong_recipient,
)


def _resp(status: int, body: str, method: str = "POST") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.request = MagicMock()
    r.request.method = method
    return r


class TestClassifyWrongRecipient:
    def test_accepted_response_is_confirmed(self):
        r = _resp(200, '{"status":"accepted","member_created":true}')
        result = classify_wrong_recipient(r, "http://x.test/fixture/invitations/t/accept")
        assert result is not None
        assert result.kind == InviteFlawKind.RECIPIENT_NOT_BOUND
        assert result.confidence == "high"
        assert result.status == "confirmed"

    def test_joined_keyword_is_confirmed(self):
        r = _resp(200, '{"status":"joined"}')
        result = classify_wrong_recipient(r, "http://x.test/invite/t/accept")
        assert result is not None

    def test_workspace_member_keyword_is_confirmed(self):
        r = _resp(200, '{"workspace_member":true}')
        result = classify_wrong_recipient(r, "http://x.test/invite/t/accept")
        assert result is not None

    def test_403_is_none(self):
        r = _resp(403, '{"error":"invite_bound_to_recipient"}')
        result = classify_wrong_recipient(r, "http://x.test/invite/t/accept")
        assert result is None

    def test_401_is_none(self):
        r = _resp(401, '{"error":"unauthenticated"}')
        result = classify_wrong_recipient(r, "http://x.test/invite/t/accept")
        assert result is None

    def test_200_without_accept_signal_is_none(self):
        r = _resp(200, '{"status":"pending"}')
        result = classify_wrong_recipient(r, "http://x.test/invite/t/accept")
        assert result is None


class TestClassifyReuse:
    def test_second_acceptance_is_confirmed(self):
        r = _resp(200, '{"status":"accepted","member_created":true}')
        result = classify_reuse(r, "http://x.test/fixture/invitations/t/accept")
        assert result is not None
        assert result.kind == InviteFlawKind.INVITE_REUSABLE
        assert result.confidence == "high"
        assert result.status == "confirmed"

    def test_410_gone_is_none(self):
        r = _resp(410, '{"error":"invite_expired"}')
        result = classify_reuse(r, "http://x.test/invite/t/accept")
        assert result is None

    def test_409_already_used_is_none(self):
        r = _resp(409, '{"error":"already_used"}')
        result = classify_reuse(r, "http://x.test/invite/t/accept")
        assert result is None

    def test_403_is_none(self):
        r = _resp(403, '{"error":"invite_bound_to_recipient"}')
        result = classify_reuse(r, "http://x.test/invite/t/accept")
        assert result is None

    def test_200_without_accept_signal_is_none(self):
        r = _resp(200, '{"status":"pending"}')
        result = classify_reuse(r, "http://x.test/invite/t/accept")
        assert result is None


class TestClassifyRoleEscalation:
    def test_admin_for_member_request_is_confirmed(self):
        r = _resp(200, '{"role":"admin"}')
        result = classify_role_escalation(
            r, "http://x.test/invite/t/accept",
            requested_role="member", observed_role="admin",
        )
        assert result is not None
        assert result.kind == InviteFlawKind.ROLE_ESCALATION
        assert result.confidence == "high"
        assert result.status == "confirmed"
        assert result.requested_role == "member"
        assert result.observed_role == "admin"

    def test_owner_for_viewer_request_is_confirmed(self):
        r = _resp(200, '{"role":"owner"}')
        result = classify_role_escalation(
            r, "http://x.test/invite/t/accept",
            requested_role="viewer", observed_role="owner",
        )
        assert result is not None

    def test_same_role_is_none(self):
        r = _resp(200, '{"role":"member"}')
        result = classify_role_escalation(
            r, "http://x.test/invite/t/accept",
            requested_role="member", observed_role="member",
        )
        assert result is None

    def test_lower_role_is_none(self):
        r = _resp(200, '{"role":"viewer"}')
        result = classify_role_escalation(
            r, "http://x.test/invite/t/accept",
            requested_role="member", observed_role="viewer",
        )
        assert result is None

    def test_no_observed_role_is_none(self):
        r = _resp(200, '{}')
        result = classify_role_escalation(
            r, "http://x.test/invite/t/accept",
            requested_role="member", observed_role=None,
        )
        assert result is None

    def test_non_200_is_none(self):
        r = _resp(404, '')
        result = classify_role_escalation(
            r, "http://x.test/invite/t/accept",
            requested_role="member", observed_role="admin",
        )
        assert result is None
