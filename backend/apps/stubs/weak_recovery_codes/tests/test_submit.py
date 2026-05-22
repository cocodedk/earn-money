"""Unit tests for `weak_recovery_codes.submit`."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from apps.stubs._shared.auth.tests._post_paths_helpers import patch_client
from apps.stubs.weak_recovery_codes.submit import (
    extract_codes_from, generate_recovery_codes,
)


_TARGET = "apps.stubs.weak_recovery_codes.submit.Client"


def _ok(status: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    return r


# ---- generate_recovery_codes ----------------------------------------

def test_generate_first_non_404() -> None:
    queue = [_ok(200), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = generate_recovery_codes(
            base_url="https://x.example", bearer_token="t",
        )
    assert resp is not None and resp.status_code == 200


def test_generate_skips_404_405() -> None:
    queue = [_ok(404), _ok(405), _ok(200)]
    with patch_client(_TARGET, queue):
        resp = generate_recovery_codes(
            base_url="https://x.example", bearer_token="t",
        )
    assert resp is not None and resp.status_code == 200


def test_generate_all_404_returns_last() -> None:
    queue = [_ok(404)] * 4
    with patch_client(_TARGET, queue):
        resp = generate_recovery_codes(
            base_url="https://x.example", bearer_token="t",
        )
    assert resp is not None and resp.status_code == 404


def test_generate_all_transport_errors() -> None:
    queue: list = [httpx.ConnectError("boom")] * 4
    with patch_client(_TARGET, queue):
        resp = generate_recovery_codes(
            base_url="https://x.example", bearer_token="t",
        )
    assert resp is None


# ---- extract_codes_from ---------------------------------------------

def _resp_json(body) -> MagicMock:
    r = MagicMock()
    r.json.return_value = body
    return r


def test_extract_top_level_codes() -> None:
    assert extract_codes_from(_resp_json(
        {"codes": ["a", "b", "c"]},
    )) == ["a", "b", "c"]


def test_extract_recovery_codes_snake_case() -> None:
    assert extract_codes_from(_resp_json(
        {"recovery_codes": ["x", "y"]},
    )) == ["x", "y"]


def test_extract_recovery_codes_camelcase() -> None:
    assert extract_codes_from(_resp_json(
        {"recoveryCodes": ["m", "n"]},
    )) == ["m", "n"]


def test_extract_top_level_array() -> None:
    assert extract_codes_from(_resp_json(["x", "y", "z"])) == ["x", "y", "z"]


def test_extract_nested_codes() -> None:
    body = {"data": {"codes": ["c1", "c2"]}}
    assert extract_codes_from(_resp_json(body)) == ["c1", "c2"]


def test_extract_non_string_array_skipped() -> None:
    """An `codes` array containing non-strings doesn't yield codes."""
    body = {"codes": [1, 2, 3]}
    assert extract_codes_from(_resp_json(body)) == []


def test_extract_non_json_body_returns_empty() -> None:
    r = MagicMock()
    r.json.side_effect = ValueError("not json")
    assert extract_codes_from(r) == []


def test_extract_non_dict_non_array_returns_empty() -> None:
    """JSON body is just a string → no codes."""
    assert extract_codes_from(_resp_json("just-a-string")) == []


def test_extract_depth_bound() -> None:
    """`{a: {b: {c: {d: {codes: [...]}}}}}` is deeper than the
    depth=3 walker; nothing returned."""
    body = {"a": {"b": {"c": {"d": {"codes": ["too-deep"]}}}}}
    assert extract_codes_from(_resp_json(body)) == []


def test_extract_top_level_array_with_non_strings() -> None:
    """Top-level array filters out non-strings."""
    assert extract_codes_from(_resp_json(["a", 1, "b", None])) == ["a", "b"]
