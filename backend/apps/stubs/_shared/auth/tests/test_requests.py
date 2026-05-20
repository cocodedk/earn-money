"""Contract tests for `_shared/auth/requests.build_probe_pair`.

Shape-preservation tests (method, content-type, UA, parameter names,
password sharing, hidden fields). CSRF-refresh tests live in the
sibling `test_requests_csrf.py` so each file stays under the 200-line
cap.

Spec 2.1 §2.6: invalid + valid control requests share method,
parameter names, content type, header set (except dynamic cookies
+ per-request CSRF), redirect policy, and User-Agent.
"""
from __future__ import annotations

import dataclasses

import pytest

from apps.stubs._shared.auth.forms import AuthForm
from apps.stubs._shared.auth.requests import (
    SCANNER_USER_AGENT, ProbePair, build_probe_pair,
)
from apps.stubs._shared.auth.tests._requests_helpers import make_form


# ----- happy path ---------------------------------------------------

def test_probe_pair_has_both_requests_when_valid_id_provided() -> None:
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="scanner-deadbeef@example.invalid",
        valid_identifier="scanner-fixture-1@example.invalid",
        bogus_password="bogus-passphrase",
    )
    assert pair.valid_request is not None
    assert isinstance(pair, ProbePair)


def test_probe_pair_valid_request_is_none_without_valid_id() -> None:
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="scanner-deadbeef@example.invalid",
        valid_identifier=None,
        bogus_password="bogus-passphrase",
    )
    assert pair.valid_request is None


# ----- shape preservation -------------------------------------------

def test_both_requests_share_method() -> None:
    pair = build_probe_pair(
        form=make_form(method="POST"),
        invalid_identifier="inv@example.invalid",
        valid_identifier="val@example.invalid",
        bogus_password="bp",
    )
    assert pair.invalid_request.method == "POST"
    assert pair.valid_request.method == "POST"


def test_both_requests_share_content_type() -> None:
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="inv@example.invalid",
        valid_identifier="val@example.invalid",
        bogus_password="bp",
    )
    inv_ct = pair.invalid_request.headers.get("content-type")
    val_ct = pair.valid_request.headers.get("content-type")
    assert inv_ct == val_ct
    assert inv_ct == "application/x-www-form-urlencoded"


def test_both_requests_carry_scanner_user_agent() -> None:
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="inv@example.invalid",
        valid_identifier="val@example.invalid",
        bogus_password="bp",
    )
    assert pair.invalid_request.headers["user-agent"] == SCANNER_USER_AGENT
    assert pair.valid_request.headers["user-agent"] == SCANNER_USER_AGENT


def test_both_requests_share_parameter_names() -> None:
    """Only the identifier VALUE differs; parameter names match."""
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="inv@example.invalid",
        valid_identifier="val@example.invalid",
        bogus_password="bp",
    )
    inv_body = pair.invalid_request.content.decode()
    val_body = pair.valid_request.content.decode()
    assert "email=" in inv_body and "email=" in val_body
    assert "password=" in inv_body and "password=" in val_body
    assert "csrf=" in inv_body and "csrf=" in val_body


def test_invalid_identifier_value_appears_only_in_invalid_request() -> None:
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="scanner-deadbeef@example.invalid",
        valid_identifier="real-user@example.invalid",
        bogus_password="bp",
    )
    inv_body = pair.invalid_request.content.decode()
    val_body = pair.valid_request.content.decode()
    assert "scanner-deadbeef" in inv_body
    assert "scanner-deadbeef" not in val_body
    assert "real-user" in val_body
    assert "real-user" not in inv_body


def test_password_value_shared_between_both_requests() -> None:
    """Spec 2.1 §2.6 — same bogus password in both probes keeps the
    request shape comparable; only the identifier differs."""
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="inv@example.invalid",
        valid_identifier="val@example.invalid",
        bogus_password="shared-bogus-pw",
    )
    assert "password=shared-bogus-pw" in pair.invalid_request.content.decode()
    assert "password=shared-bogus-pw" in pair.valid_request.content.decode()


def test_hidden_fields_from_form_included() -> None:
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="inv@example.invalid",
        valid_identifier=None,
        bogus_password="bp",
    )
    body = pair.invalid_request.content.decode()
    assert "csrf=tok-A" in body


def test_password_omitted_when_form_has_no_password_field() -> None:
    """Reset / identifier-enum-only flows omit the password parameter."""
    form = AuthForm(
        method="POST", action_url="https://x.test/reset",
        content_type="application/x-www-form-urlencoded",
        identifier_field="email", password_field=None,
        hidden_fields={}, flow_hint="password_reset",
    )
    pair = build_probe_pair(
        form=form,
        invalid_identifier="inv@example.invalid",
        valid_identifier=None,
        bogus_password="bp",
    )
    body = pair.invalid_request.content.decode()
    assert "password" not in body
    assert "email=inv" in body


# ----- frozen dataclass ---------------------------------------------

def test_probe_pair_is_frozen() -> None:
    pair = build_probe_pair(
        form=make_form(),
        invalid_identifier="inv@example.invalid",
        valid_identifier=None,
        bogus_password="bp",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        pair.form = None  # type: ignore[misc]
