"""Edge-case tests for `_shared/auth/_forms_html`.

Covers uncovered branches:
- method not in GET/POST → coerced to POST
- find_named_input with type_filter where name is None
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from apps.stubs._shared.auth._forms_html import find_named_input, parse_form


def _tag(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("form")


def test_method_not_get_or_post_coerced_to_post() -> None:
    """A form using method='PUT' (unusual but valid HTML5) is normalised
    to POST — spec 2.1 only handles GET / POST at submission time."""
    form_tag = _tag(
        '<form method="PUT" action="/login">'
        '<input name="email">'
        '<input name="password" type="password">'
        "</form>"
    )
    result = parse_form(form_tag, "https://x.example")
    assert result is not None
    assert result["method"] == "POST"


def test_method_delete_coerced_to_post() -> None:
    """Another non-GET/POST method (DELETE) also normalises to POST."""
    form_tag = _tag(
        '<form method="DELETE" action="/auth">'
        '<input name="username">'
        '<input name="password" type="password">'
        "</form>"
    )
    result = parse_form(form_tag, "https://x.example")
    assert result is not None
    assert result["method"] == "POST"


def test_find_named_input_skips_input_with_no_name() -> None:
    """When an input has the right type but no `name` attribute,
    find_named_input skips it and returns None if no named input
    follows."""
    soup = BeautifulSoup(
        '<input type="password"><input type="text" name="user">',
        "html.parser",
    )
    inputs = soup.find_all("input")
    # type_filter=password → only matches the nameless input → None
    result = find_named_input(inputs, type_filter="password")
    assert result is None


def test_find_named_input_returns_second_when_first_nameless() -> None:
    """The nameless input is skipped; the second named password input wins."""
    soup = BeautifulSoup(
        '<input type="password">'
        '<input type="password" name="pass">',
        "html.parser",
    )
    inputs = soup.find_all("input")
    result = find_named_input(inputs, type_filter="password")
    assert result == "pass"
