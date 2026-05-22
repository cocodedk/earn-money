"""HTML-parsing internals for `forms.discover_forms`.

Split out of `forms.py` to stay under the 200-line cap; the public
surface (`AuthForm` + `discover_forms` + `discover_json_endpoints`)
lives in `forms.py` and delegates here.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Literal
from urllib.parse import urljoin

from bs4.element import Tag

from ..body_match import contains_any_lowered


# Identifier-input names in detection-priority order. The first match
# becomes the form's `identifier_field`. Spec 2.1 §1 lists these as
# the canonical signals.
IDENTIFIER_NAMES: tuple[str, ...] = (
    "email",
    "username",
    "login",
    "identifier",
    "user",
    "account",
)

FlowHint = Literal["login", "password_reset", "registration", "oauth", "unknown"]

_FLOW_HINTS: tuple[tuple[FlowHint, tuple[str, ...]], ...] = (
    ("password_reset", ("reset", "forgot", "recover")),
    ("registration", ("signup", "sign-up", "register", "create")),
    ("oauth", ("oauth", "sso", "openid")),
    ("login", ("login", "signin", "sign-in", "auth")),
)


def parse_form(form_tag: Tag, base_url: str) -> dict | None:
    """Return a dict of `AuthForm` kwargs if the tag is an auth
    candidate, else None. Per spec 2.1 §1, "password field OR
    identifier-named input" is sufficient; either alone qualifies.
    """
    inputs = form_tag.find_all("input")
    password_field = find_named_input(inputs, type_filter="password")
    identifier_field = find_identifier_field(inputs)
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
    return {
        "method": method,
        "action_url": action_url,
        "content_type": "application/x-www-form-urlencoded",
        "identifier_field": identifier_field,
        "password_field": password_field,
        "hidden_fields": hidden_fields,
        "flow_hint": infer_flow_hint(action_url),
    }


def find_named_input(
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


def find_identifier_field(inputs: Iterable[Tag]) -> str | None:
    """Return the first input whose `name` matches one of the canonical
    identifier names, preferring earlier entries in IDENTIFIER_NAMES."""
    present: dict[str, None] = {}
    for inp in inputs:
        name = inp.get("name")
        if name and name in IDENTIFIER_NAMES:
            present[name] = None
    for candidate in IDENTIFIER_NAMES:
        if candidate in present:
            return candidate
    return None


def infer_flow_hint(action_url: str) -> FlowHint:
    """Best-effort flow classification from substrings in the action URL."""
    lo = action_url.lower()
    for hint, tokens in _FLOW_HINTS:
        if contains_any_lowered(lo, tokens):
            return hint
    return "unknown"
