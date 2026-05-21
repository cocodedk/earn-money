"""Auth-form discovery — HTML and JSON.

Parses a server's response body for forms or API endpoints that look
like authentication surfaces. Stubs 2.1 through 2.22 all consume this
helper before constructing probes.

Detection is duck-typed: a form is an auth candidate if it has a
`<input type="password">` OR any input named like `email | username |
login | identifier | user | account` (spec 2.1 §1). Either alone
qualifies — a password-only form (PIN entry, sudo-confirm, second
step of multi-page login) is still discovered.

Out of scope: JavaScript-rendered SPAs. A sparse body returns `[]`;
the runner emits `AUTH_FIXTURE_REQUIRED` with
`reason="requires_js_rendering"` (Phase 3 work).

Internals split into `_forms_html.py` to keep this file under the
200-line cap.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import _forms_html as _html


@dataclass(frozen=True)
class AuthForm:
    """One discovered authentication surface — HTML form or JSON endpoint.

    Either `identifier_field` or `password_field` is non-None (or both).
    A password-only form (e.g. PIN entry, sudo-confirm, second step of
    a multi-page login) is still an auth candidate; discovery doesn't
    enforce which inputs the stub needs.
    """
    method: Literal["GET", "POST"]
    action_url: str
    content_type: str
    identifier_field: str | None
    password_field: str | None
    hidden_fields: dict[str, str]
    flow_hint: _html.FlowHint


def discover_forms(
    html_body: str, base_url: str,
    *, response_content_type: str = "text/html",
) -> list[AuthForm]:
    """Return every auth-candidate `<form>` in ``html_body``.

    Non-HTML content-types and empty bodies return `[]`. The parser
    uses Python's bundled `html.parser` (no lxml dependency).
    """
    if "html" not in response_content_type.lower():
        return []
    if not html_body:
        return []
    soup = BeautifulSoup(html_body, "html.parser")
    out: list[AuthForm] = []
    for form_tag in soup.find_all("form"):
        kwargs = _html.parse_form(form_tag, base_url)
        if kwargs is not None:
            out.append(AuthForm(**kwargs))
    return out


def pick_login_form(forms: list[AuthForm]) -> AuthForm | None:
    """First form with `flow_hint=login` AND a `password_field`.

    Without a password field there's no credential surface to probe;
    such forms are skipped. Used by every Phase 2 login stub
    (lockout / rate-limit / etc.).
    """
    for f in forms:
        if f.flow_hint == "login" and f.password_field is not None:
            return f
    return None


def discover_json_endpoints(
    response_body: bytes, base_url: str,
    *, response_content_type: str,
) -> list[AuthForm]:
    """Parse a JSON route-listing response for login-like endpoints.

    Expected shape: `{"routes": [{"path": "/...", "method": "POST"}, ...]}`.
    Routes whose path contains an auth keyword (`login`, `signin`,
    `reset`, etc.) become `AuthForm` records with `content_type=
    application/json`.
    """
    if "json" not in response_content_type.lower():
        return []
    try:
        data = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    routes = data.get("routes")
    if not isinstance(routes, list):
        return []

    out: list[AuthForm] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        path = route.get("path")
        if not isinstance(path, str):
            continue
        hint = _html.infer_flow_hint(path)
        if hint == "unknown":
            continue
        method = route.get("method", "POST")
        if method not in ("GET", "POST"):
            continue
        out.append(AuthForm(
            method=method,
            action_url=urljoin(base_url, path),
            content_type="application/json",
            identifier_field="identifier",
            password_field=None,
            hidden_fields={},
            flow_hint=hint,
        ))
    return out
