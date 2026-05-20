"""Auth-form discovery — HTML and JSON.

Parses a server's response body for forms or API endpoints that look
like authentication surfaces. Stubs 2.1 through 2.22 all consume this
helper before constructing probes.

Detection is duck-typed: a form is an auth candidate if it has a
`<input type="password">` OR any input named like `email | username |
login | identifier | user | account`. Action URLs are resolved to
absolute via `urljoin`. `flow_hint` is best-effort guidance derived
from the action URL — the runner still treats every form generically.

Out of scope: JavaScript-rendered SPAs. A sparse body returns `[]`;
the runner emits `AUTH_FIXTURE_REQUIRED` with
`reason="requires_js_rendering"` (Phase 3 work).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from ..body_match import contains_any_lowered


# Identifier-input names in detection-priority order. The first match
# becomes the form's `identifier_field`. Spec 2.1 §1 lists these as
# the canonical signals.
_IDENTIFIER_NAMES: tuple[str, ...] = (
    "email",
    "username",
    "login",
    "identifier",
    "user",
    "account",
)

_FLOW_HINTS: tuple[tuple[Literal["login", "password_reset", "registration", "oauth", "unknown"], tuple[str, ...]], ...] = (
    ("password_reset", ("reset", "forgot", "recover")),
    ("registration", ("signup", "sign-up", "register", "create")),
    ("oauth", ("oauth", "sso", "openid")),
    ("login", ("login", "signin", "sign-in", "auth")),
)


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
    flow_hint: Literal["login", "password_reset", "registration", "oauth", "unknown"]


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
        form = _parse_form(form_tag, base_url)
        if form is not None:
            out.append(form)
    return out


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
        hint = _infer_flow_hint(path)
        if hint == "unknown":
            continue
        method = route.get("method", "POST")
        if method not in ("GET", "POST"):
            continue
        out.append(AuthForm(
            method=method,
            action_url=urljoin(base_url, path),
            content_type="application/json",
            identifier_field="identifier",  # generic — JSON shape opaque
            password_field=None,
            hidden_fields={},
            flow_hint=hint,
        ))
    return out


# ----- internals ------------------------------------------------------


def _parse_form(form_tag: Tag, base_url: str) -> AuthForm | None:
    """Return an `AuthForm` if the tag is an auth candidate, else None.

    Per spec 2.1 §1, "password field OR identifier-named input" is
    sufficient; either alone discovers the form. The runner decides
    whether its specific stub can use a password-only or
    identifier-only candidate.
    """
    inputs = form_tag.find_all("input")
    password_field = _find_named_input(inputs, type_filter="password")
    identifier_field = _find_identifier_field(inputs)
    if identifier_field is None and password_field is None:
        return None

    method = (form_tag.get("method") or "GET").upper()
    if method not in ("GET", "POST"):
        method = "POST"

    action = form_tag.get("action") or base_url
    action_url = urljoin(base_url, action)
    hidden_fields = {
        inp.get("name"): inp.get("value") or ""
        for inp in inputs
        if inp.get("type") == "hidden" and inp.get("name")
    }
    flow_hint = _infer_flow_hint(action_url)

    return AuthForm(
        method=method,
        action_url=action_url,
        content_type="application/x-www-form-urlencoded",
        identifier_field=identifier_field,
        password_field=password_field,
        hidden_fields=hidden_fields,
        flow_hint=flow_hint,
    )


def _find_named_input(
    inputs: Iterable[Tag], *, type_filter: str | None = None,
) -> str | None:
    """Return the `name` of the first input matching ``type_filter``."""
    for inp in inputs:
        if type_filter and inp.get("type") != type_filter:
            continue
        name = inp.get("name")
        if name:
            return name
    return None


def _find_identifier_field(inputs: Iterable[Tag]) -> str | None:
    """Return the first input whose `name` matches one of the canonical
    identifier names, preferring earlier entries in _IDENTIFIER_NAMES."""
    present: dict[str, None] = {}
    for inp in inputs:
        name = inp.get("name")
        if not name:
            continue
        if name in _IDENTIFIER_NAMES:
            present[name] = None
    for candidate in _IDENTIFIER_NAMES:
        if candidate in present:
            return candidate
    return None


def _infer_flow_hint(action_url: str) -> Literal["login", "password_reset", "registration", "oauth", "unknown"]:
    """Best-effort flow classification from substrings in the action URL."""
    lo = action_url.lower()
    for hint, tokens in _FLOW_HINTS:
        if contains_any_lowered(lo, tokens):
            return hint
    return "unknown"
