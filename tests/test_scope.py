from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import scope


def test_read_scope_from_fixture(fixtures_dir: Path) -> None:
    s = scope.read_scope(fixtures_dir / "scope_example.md")
    assert s.platform == "hackerone"
    assert s.slug == "example"
    assert s.policy == "rate-limited-OK"
    assert s.in_scope == ["*.example.com", "api.example.org"]
    assert s.out_of_scope == ["blog.example.com"]
    assert "Target intuition" in s.notes


def test_hash_is_stable_under_reordering() -> None:
    a = scope.Scope(
        platform="x", slug="y", policy="rate-limited-OK",
        in_scope=["a", "b", "c"], out_of_scope=["d"], notes="",
        scope_hash="", last_synced="",
    )
    b = scope.Scope(
        platform="x", slug="y", policy="rate-limited-OK",
        in_scope=["c", "a", "b"], out_of_scope=["d"], notes="",
        scope_hash="", last_synced="",
    )
    assert scope.compute_hash(a) == scope.compute_hash(b)


def test_hash_changes_when_in_scope_changes() -> None:
    a = scope.Scope(
        platform="x", slug="y", policy="rate-limited-OK",
        in_scope=["a"], out_of_scope=[], notes="",
        scope_hash="", last_synced="",
    )
    b = scope.Scope(
        platform="x", slug="y", policy="rate-limited-OK",
        in_scope=["a", "b"], out_of_scope=[], notes="",
        scope_hash="", last_synced="",
    )
    assert scope.compute_hash(a) != scope.compute_hash(b)


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["a.example.com"], out_of_scope=[], notes="hello",
        scope_hash="deadbeef", last_synced="2026-05-12T08:00:00Z",
    )
    path = tmp_path / "scope.md"
    scope.write_scope(path, s)
    loaded = scope.read_scope(path)
    assert loaded == s


def test_invalid_policy_rejected(tmp_path: Path) -> None:
    path = tmp_path / "scope.md"
    path.write_text(
        "---\nplatform: x\nslug: y\npolicy: bogus\nscope_hash: ''\nlast_synced: ''\n"
        "in_scope: []\nout_of_scope: []\n---\nbody",
        encoding="utf-8",
    )
    with pytest.raises(scope.InvalidScope):
        scope.read_scope(path)


def test_malformed_yaml_translated_to_invalid_scope(tmp_path: Path) -> None:
    """A YAMLError from the parser must surface as InvalidScope so callers
    can catch a single, narrow exception type."""
    path = tmp_path / "scope.md"
    path.write_text(
        "---\nplatform: x\nslug: y\npolicy: [unclosed\n---\nbody",
        encoding="utf-8",
    )
    with pytest.raises(scope.InvalidScope, match="malformed YAML"):
        scope.read_scope(path)


def test_missing_required_key_translated_to_invalid_scope(tmp_path: Path) -> None:
    """A KeyError from accessing a missing `platform:` (or `slug:`) must
    surface as InvalidScope so callers can keep their except clauses narrow."""
    path = tmp_path / "scope.md"
    path.write_text(
        "---\nslug: y\npolicy: rate-limited-OK\nscope_hash: ''\nlast_synced: ''\n"
        "in_scope: []\nout_of_scope: []\n---\nbody",
        encoding="utf-8",
    )
    with pytest.raises(scope.InvalidScope, match="missing required key"):
        scope.read_scope(path)
