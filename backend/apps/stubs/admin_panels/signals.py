"""Signal detection for stub 1.8 exposed-admin-panels.

Per spec §Candidate response signals, a path is "interesting" when:
- status is 200, 401, or 403; OR
- body contains login-form markers; OR
- body contains admin-panel/management-console terms.

Plus the soft-404 comparison handled at the runner level.

Each signal extractor is pure (no I/O) and returns a tuple
(triggered: bool, kind: str) so the runner can aggregate the strongest
signal per path.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/08-exposed-admin-panels.md
"""
from __future__ import annotations

from .._shared.body_match import contains_any


_AUTH_STATUSES = {401, 403}
_OK_STATUS = 200


# Body markers — case-insensitive substring match on lowered body text.
# Login-form markers are stronger than generic admin terms because they
# imply an actual auth interface vs prose mentioning admin work.
_LOGIN_FORM_MARKERS: tuple[str, ...] = (
    'type="password"',
    "name=\"password\"",
    "id=\"password\"",
    'autocomplete="current-password"',
    'name="csrf"',
    "csrf-token",
)

_ADMIN_PANEL_MARKERS: tuple[str, ...] = (
    "admin dashboard",
    "admin panel",
    "administrator login",
    "control panel",
    "management console",
    "site administration",
)


def has_login_form(body: str) -> bool:
    return contains_any(body, _LOGIN_FORM_MARKERS)


def has_admin_panel_marker(body: str) -> bool:
    return contains_any(body, _ADMIN_PANEL_MARKERS)


def is_auth_status(status: int) -> bool:
    return status in _AUTH_STATUSES


def is_ok_status(status: int) -> bool:
    return status == _OK_STATUS
