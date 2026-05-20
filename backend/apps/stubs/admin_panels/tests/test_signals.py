"""Signal-detection tests for stub 1.8."""
from __future__ import annotations

import unittest

from ..signals import (
    has_admin_panel_marker,
    has_login_form,
    is_auth_status,
    is_ok_status,
)


class LoginFormTests(unittest.TestCase):
    def test_password_input_detected(self) -> None:
        assert has_login_form('<input type="password" name="pw">')

    def test_csrf_token_detected(self) -> None:
        assert has_login_form('<meta name="csrf-token" content="xyz">')

    def test_uppercase_match(self) -> None:
        # `lower()` first → matcher tolerates Type="Password".
        assert has_login_form('Type="Password"')

    def test_no_match_on_prose(self) -> None:
        assert not has_login_form("This page explains password security.")

    def test_empty_body(self) -> None:
        assert not has_login_form("")


class AdminPanelMarkerTests(unittest.TestCase):
    def test_admin_dashboard_detected(self) -> None:
        assert has_admin_panel_marker("Welcome to the Admin Dashboard")

    def test_administrator_login_detected(self) -> None:
        assert has_admin_panel_marker("<h1>Administrator Login</h1>")

    def test_no_match_on_neutral_prose(self) -> None:
        assert not has_admin_panel_marker("our team manages this carefully")

    def test_empty_body(self) -> None:
        assert not has_admin_panel_marker("")


class StatusTests(unittest.TestCase):
    def test_auth_statuses(self) -> None:
        assert is_auth_status(401)
        assert is_auth_status(403)
        assert not is_auth_status(200)
        assert not is_auth_status(404)

    def test_ok_status(self) -> None:
        assert is_ok_status(200)
        assert not is_ok_status(401)
        assert not is_ok_status(302)
