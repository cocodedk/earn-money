"""Tests for stub 2.5's reset-form discovery module.

fetch_and_find_reset_form is mocked at the runner level in test_detection.py;
here we test the real function with a mocked httpx.Client to cover the
branches in discovery.py lines 30-74.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.stubs.predictable_reset_token.discovery import (
    DiscoveryOutcome,
    fetch_and_find_reset_form,
)
from apps.stubs.predictable_reset_token.tests._helpers import _mock_response


_RESET_HTML = (
    "<html><body>"
    '<form method="POST" action="/password-reset">'
    '<input name="email" type="email">'
    "</form></body></html>"
)

_LOGIN_HTML = (
    "<html><body>"
    '<form method="POST" action="/login">'
    '<input name="email">'
    '<input name="password" type="password">'
    "</form></body></html>"
)

_RESET_PATH_HTML = (
    "<html><body>"
    '<form method="POST" action="/forgot">'
    '<input name="email" type="email">'
    "</form></body></html>"
)


def test_reset_form_found_at_base_url() -> None:
    """Home page contains a reset form → outcome.form is set, no error."""
    resp = _mock_response(body=_RESET_HTML, url="https://x.example/")
    with patch(
        "apps.stubs.predictable_reset_token.discovery.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.get.return_value = resp
        outcome = fetch_and_find_reset_form("https://x.example")
    assert outcome.form is not None
    assert outcome.form.flow_hint == "password_reset"
    assert outcome.error is None


def test_transport_error_on_home_returns_error_outcome() -> None:
    """RequestError on the initial GET → outcome.error is set, form=None."""
    import httpx
    with patch(
        "apps.stubs.predictable_reset_token.discovery.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.ConnectError("refused")
        )
        outcome = fetch_and_find_reset_form("https://x.example")
    assert outcome.form is None
    assert outcome.error == "ConnectError"


def test_no_reset_form_at_home_falls_back_to_candidate_paths() -> None:
    """Home has a login form only; the fallback probes one candidate path
    that contains a reset form."""
    home_resp = _mock_response(body=_LOGIN_HTML, url="https://x.example/")
    reset_resp = _mock_response(body=_RESET_PATH_HTML,
                                url="https://x.example/forgot-password")

    call_count = [0]

    def _get(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return home_resp
        return reset_resp

    with patch(
        "apps.stubs.predictable_reset_token.discovery.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.get.side_effect = _get
        with patch(
            "apps.stubs.predictable_reset_token.discovery.candidate_reset_paths",
            return_value=["/forgot-password"],
        ):
            outcome = fetch_and_find_reset_form("https://x.example")
    assert outcome.form is not None
    assert outcome.error is None


def test_transport_error_on_candidate_path_continues() -> None:
    """RequestError on a candidate-path GET is swallowed and the loop
    continues — if all paths fail, outcome.form is None."""
    import httpx
    home_resp = _mock_response(body=_LOGIN_HTML, url="https://x.example/")
    call_count = [0]

    def _get(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return home_resp
        raise httpx.ConnectError("refused")

    with patch(
        "apps.stubs.predictable_reset_token.discovery.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.get.side_effect = _get
        with patch(
            "apps.stubs.predictable_reset_token.discovery.candidate_reset_paths",
            return_value=["/forgot-password"],
        ):
            outcome = fetch_and_find_reset_form("https://x.example")
    assert outcome.form is None
    assert outcome.error is None  # only the home GET populates error


def test_no_reset_form_anywhere_returns_none_form_no_error() -> None:
    """Neither home nor any candidate path has a reset form → form=None,
    error=None, final_url is the home URL."""
    home_resp = _mock_response(body=_LOGIN_HTML, url="https://x.example/")
    no_form_resp = _mock_response(body="<html><body></body></html>",
                                  url="https://x.example/other")

    call_count = [0]

    def _get(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return home_resp
        return no_form_resp

    with patch(
        "apps.stubs.predictable_reset_token.discovery.Client",
    ) as cls:
        cls.return_value.__enter__.return_value.get.side_effect = _get
        with patch(
            "apps.stubs.predictable_reset_token.discovery.candidate_reset_paths",
            return_value=["/no-reset-here"],
        ):
            outcome = fetch_and_find_reset_form("https://x.example")
    assert outcome.form is None
    assert outcome.error is None
    assert "x.example" in outcome.final_url
