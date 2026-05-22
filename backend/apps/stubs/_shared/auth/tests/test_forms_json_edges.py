"""Edge-case tests for `forms.discover_json_endpoints`.

test_forms.py is already over the 200-line cap; JSON-discovery edge
cases live here.

Covers:
- body decodes to a non-dict
- routes is not a list
- a route entry is not a dict
- a route entry has no 'path' key or path is not a string
- route path yields flow_hint == 'unknown' → skipped
- route method is not GET/POST → skipped
"""
from __future__ import annotations

import json

from apps.stubs._shared.auth.forms import discover_json_endpoints


BASE = "https://example.invalid"


def _body(obj) -> bytes:
    return json.dumps(obj).encode()


def test_non_dict_body_returns_empty() -> None:
    """Top-level JSON array is not a dict → []."""
    assert discover_json_endpoints(
        b'[{"routes": []}]', BASE,
        response_content_type="application/json",
    ) == []


def test_routes_not_a_list_returns_empty() -> None:
    """When 'routes' is a string instead of a list → []."""
    assert discover_json_endpoints(
        _body({"routes": "not-a-list"}), BASE,
        response_content_type="application/json",
    ) == []


def test_route_entry_not_a_dict_skipped() -> None:
    """A route entry that is an integer (not a dict) is skipped while
    the subsequent valid route is still extracted."""
    result = discover_json_endpoints(
        _body({"routes": [42, {"path": "/login", "method": "POST"}]}), BASE,
        response_content_type="application/json",
    )
    assert len(result) == 1


def test_route_missing_path_skipped() -> None:
    """A route dict without a 'path' key is skipped."""
    result = discover_json_endpoints(
        _body({"routes": [{"method": "POST"}]}), BASE,
        response_content_type="application/json",
    )
    assert result == []


def test_route_path_not_a_string_skipped() -> None:
    """A route dict with a non-string 'path' value is skipped."""
    result = discover_json_endpoints(
        _body({"routes": [{"path": 123, "method": "POST"}]}), BASE,
        response_content_type="application/json",
    )
    assert result == []


def test_route_with_unknown_flow_hint_skipped() -> None:
    """A route whose path contains no auth keyword → hint=='unknown' → skipped."""
    result = discover_json_endpoints(
        _body({"routes": [{"path": "/api/v1/data", "method": "POST"}]}), BASE,
        response_content_type="application/json",
    )
    assert result == []


def test_route_with_unsupported_method_skipped() -> None:
    """A route method that is not GET or POST (e.g. DELETE) is skipped."""
    result = discover_json_endpoints(
        _body({"routes": [{"path": "/api/v1/login", "method": "DELETE"}]}), BASE,
        response_content_type="application/json",
    )
    assert result == []


def test_valid_get_route_accepted() -> None:
    """A GET route with an auth keyword is accepted (as well as POST)."""
    result = discover_json_endpoints(
        _body({"routes": [{"path": "/api/login", "method": "GET"}]}), BASE,
        response_content_type="application/json",
    )
    assert len(result) == 1
    assert result[0].method == "GET"
