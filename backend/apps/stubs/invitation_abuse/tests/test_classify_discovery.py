"""Tests for stub 2.21 invitation-abuse classifier — discovery phase."""
from __future__ import annotations

from unittest.mock import MagicMock

from apps.stubs.invitation_abuse.classify import (
    InviteFlawKind,
    classify_invite_surface,
    classify_preview_exposure,
)


def _resp(status: int, body: str, method: str = "GET") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = body
    r.request = MagicMock()
    r.request.method = method
    return r


class TestClassifyInviteSurface:
    def test_invite_path_with_invite_body_is_candidate(self):
        r = _resp(200, '{"invite_creation_url":"/fixture/invitations"}')
        result = classify_invite_surface(r, "http://x.test/fixture/invitations")
        assert result is not None
        assert result.kind == InviteFlawKind.SENSITIVE_PREVIEW
        assert result.status == "candidate"
        assert result.confidence == "low"

    def test_invite_path_but_no_invite_keyword_in_body_is_none(self):
        r = _resp(200, '{"ok":true,"dashboard":true}')
        result = classify_invite_surface(r, "http://x.test/fixture/invitations")
        assert result is None

    def test_non_invite_path_is_none(self):
        r = _resp(200, '{"ok":true}')
        result = classify_invite_surface(r, "http://x.test/api/users")
        assert result is None

    def test_non_200_is_none(self):
        r = _resp(404, "Not found")
        result = classify_invite_surface(r, "http://x.test/fixture/invitations")
        assert result is None


class TestClassifyPreviewExposure:
    def test_unauthenticated_workspace_field_is_candidate(self):
        r = _resp(200, '{"workspace":"acme","role":"member","invited_by":"u@t.test"}')
        result = classify_preview_exposure(r, "http://x.test/fixture/invitations/tok1")
        assert result is not None
        assert result.kind == InviteFlawKind.SENSITIVE_PREVIEW
        assert result.confidence == "medium"
        assert result.status == "candidate"
        assert "workspace" in result.observed_fields

    def test_tenant_field_alone_triggers(self):
        r = _resp(200, '{"tenant":"acme","token":"tok"}')
        result = classify_preview_exposure(r, "http://x.test/invite/tok1")
        assert result is not None
        assert "tenant" in result.observed_fields

    def test_authenticated_request_is_none(self):
        r = _resp(200, '{"workspace":"acme","role":"member"}')
        result = classify_preview_exposure(r, "http://x.test/invite/tok", authenticated=True)
        assert result is None

    def test_404_is_none(self):
        r = _resp(404, "Not found")
        result = classify_preview_exposure(r, "http://x.test/invite/tok")
        assert result is None

    def test_no_sensitive_fields_is_none(self):
        r = _resp(200, '{"status":"pending","id":"abc"}')
        result = classify_preview_exposure(r, "http://x.test/invite/tok")
        assert result is None

    def test_post_method_is_none(self):
        r = _resp(200, '{"workspace":"acme","role":"member"}', method="POST")
        result = classify_preview_exposure(r, "http://x.test/invite/tok")
        assert result is None
