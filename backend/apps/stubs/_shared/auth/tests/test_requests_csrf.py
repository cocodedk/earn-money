"""CSRF-refresh callback tests for `build_probe_pair`.

Split from `test_requests.py` to stay under the 200-line cap.
"""
from __future__ import annotations

from apps.stubs._shared.auth.requests import build_probe_pair
from apps.stubs._shared.auth.tests._requests_helpers import make_form


def test_csrf_refresh_overrides_form_hidden_values() -> None:
    """If a callback is supplied, the per-request hidden values come
    from it, not from form.hidden_fields. The form's stored CSRF
    token is stale by submit time."""
    fresh = {"csrf": "tok-FRESH", "next": "/dashboard"}
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="inv@example.invalid",
        valid_identifier=None,
        bogus_password="bp",
        csrf_refresh=lambda: fresh,
    )
    body = pair.invalid_request.content.decode()
    assert "csrf=tok-FRESH" in body
    assert "next=%2Fdashboard" in body  # urlencoded


def test_csrf_refresh_called_once_per_request() -> None:
    """One refresh per submit, not one per pair — the spec invariant
    matches per-request CSRF rotation."""
    call_count = {"n": 0}

    def refresh() -> dict[str, str]:
        call_count["n"] += 1
        return {"csrf": f"tok-{call_count['n']}"}

    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="inv@example.invalid",
        valid_identifier="val@example.invalid",
        bogus_password="bp",
        csrf_refresh=refresh,
    )
    assert call_count["n"] == 2
    inv_body = pair.invalid_request.content.decode()
    val_body = pair.valid_request.content.decode()
    assert "csrf=tok-1" in inv_body
    assert "csrf=tok-2" in val_body
