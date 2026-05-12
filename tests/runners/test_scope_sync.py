from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from earn_money import config, flags, scope
from earn_money.platforms import hackerone
from earn_money.runners import scope_sync


def _client(fixture_path: Path) -> hackerone.Client:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return hackerone.Client(
        username="u", token="t", transport=httpx.MockTransport(handler)
    )


def _seed_scope(
    paths: config.Paths,
    slug: str,
    *,
    in_scope: list[str],
    out_of_scope: list[str],
    scope_hash: str = "",
) -> scope.Scope:
    s = scope.Scope(
        platform="hackerone", slug=slug, policy="rate-limited-OK",
        in_scope=in_scope, out_of_scope=out_of_scope, notes="seed",
        scope_hash=scope_hash, last_synced="",
    )
    scope.write_scope(paths.scope_file("hackerone", slug), s)
    return s


def test_refuses_without_recon_enabled(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths, "example", in_scope=[], out_of_scope=[])
    with pytest.raises(flags.ReconDisabled):
        scope_sync.sync_program(
            paths, "hackerone", "example",
            _client(fixtures_dir / "hackerone_program_initial.json"),
        )


def test_refuses_when_program_already_frozen(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, "example", in_scope=[], out_of_scope=[])
    flags.freeze_program(paths, "hackerone", "example", reason="prior")
    with pytest.raises(flags.ProgramFrozen):
        scope_sync.sync_program(
            paths, "hackerone", "example",
            _client(fixtures_dir / "hackerone_program_initial.json"),
        )


def test_initial_sync_records_hash_and_assets(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, "example", in_scope=[], out_of_scope=[])

    result = scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_initial.json"),
    )

    assert result.action == "updated"
    s = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert sorted(s.in_scope) == ["*.example.com", "api.example.org"]
    assert s.out_of_scope == ["blog.example.com"]
    assert s.scope_hash  # populated
    assert s.last_synced  # populated
    assert not flags.is_program_frozen(paths, "hackerone", "example")


def test_additive_diff_updates_scope(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(
        paths, "example",
        in_scope=["*.example.com", "api.example.org"],
        out_of_scope=["blog.example.com"],
    )
    # First sync to establish hash.
    scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_initial.json"),
    )

    result = scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_additive.json"),
    )

    assert result.action == "updated"
    s = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert "new.example.com" in s.in_scope
    assert not flags.is_program_frozen(paths, "hackerone", "example")


def test_destructive_diff_freezes_program(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(
        paths, "example",
        in_scope=["*.example.com", "api.example.org"],
        out_of_scope=["blog.example.com"],
    )
    scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_initial.json"),
    )

    result = scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_destructive.json"),
    )

    assert result.action == "frozen"
    assert flags.is_program_frozen(paths, "hackerone", "example")
    reason = flags.freeze_reason(paths, "hackerone", "example")
    assert "*.example.com" in reason
    # scope.md must NOT be rewritten on a destructive diff.
    s = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert "*.example.com" in s.in_scope


def test_no_change_only_updates_last_synced(tmp_repo: Path, fixtures_dir: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(
        paths, "example",
        in_scope=["*.example.com", "api.example.org"],
        out_of_scope=["blog.example.com"],
    )
    scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_initial.json"),
    )
    first = scope.read_scope(paths.scope_file("hackerone", "example"))

    result = scope_sync.sync_program(
        paths, "hackerone", "example",
        _client(fixtures_dir / "hackerone_program_initial.json"),
    )

    assert result.action == "unchanged"
    second = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert first.scope_hash == second.scope_hash
    assert first.in_scope == second.in_scope
