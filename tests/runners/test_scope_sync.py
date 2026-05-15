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
    assert second.last_synced  # populated
    assert second.last_synced >= first.last_synced


def test_api_failure_freezes_program(
    tmp_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Network/API errors during sync must freeze the program (spec line 103)."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, "example", in_scope=[], out_of_scope=[])

    monkeypatch.setenv("HACKERONE_API_USERNAME", "u")
    monkeypatch.setenv("HACKERONE_API_TOKEN", "t")

    def explode(_self: object, _slug: str) -> tuple[list[str], list[str]]:
        raise hackerone.HackerOneAPIError("boom")

    monkeypatch.setattr(hackerone.Client, "fetch_structured_scope", explode)

    rc = scope_sync.main(
        ["--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)]
    )

    assert rc != 0
    assert flags.is_program_frozen(paths, "hackerone", "example")
    reason = flags.freeze_reason(paths, "hackerone", "example")
    assert "scope-sync failed" in reason


def test_missing_credentials_freezes_program(
    tmp_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If creds are missing, the API call must still freeze the program."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, "example", in_scope=[], out_of_scope=[])

    monkeypatch.delenv("HACKERONE_API_USERNAME", raising=False)
    monkeypatch.delenv("HACKERONE_API_TOKEN", raising=False)

    def explode(_self: object, _slug: str) -> tuple[list[str], list[str]]:
        raise hackerone.HackerOneAPIError("no creds")

    monkeypatch.setattr(hackerone.Client, "fetch_structured_scope", explode)

    rc = scope_sync.main(
        ["--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)]
    )

    assert rc != 0
    assert flags.is_program_frozen(paths, "hackerone", "example")
    reason = flags.freeze_reason(paths, "hackerone", "example")
    assert "scope-sync failed" in reason


def test_empty_api_response_freezes_when_prior_scope_existed(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(
        paths, "example",
        in_scope=["*.example.com", "api.example.org"],
        out_of_scope=["blog.example.com"],
        scope_hash="prior_hash_nonempty",
    )

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    empty_client = hackerone.Client(
        username="u", token="t", transport=httpx.MockTransport(handler)
    )

    result = scope_sync.sync_program(paths, "hackerone", "example", empty_client)

    assert result.action == "frozen"
    assert flags.is_program_frozen(paths, "hackerone", "example")
    reason = flags.freeze_reason(paths, "hackerone", "example")
    assert "*.example.com" in reason
    # scope.md must NOT be rewritten on freeze.
    s = scope.read_scope(paths.scope_file("hackerone", "example"))
    assert "*.example.com" in s.in_scope
