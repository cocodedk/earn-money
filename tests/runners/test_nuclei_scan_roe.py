"""Tests for `nuclei_scan_cli.resolve_rate_limit` — the bridge between
`roe.md` and the nuclei `-rl` flag."""

from __future__ import annotations

from pathlib import Path

from earn_money import config
from earn_money.runners import nuclei_scan_cli


def _write_roe(paths: config.Paths, content: str) -> None:
    target = paths.roe_file("hackerone", "example")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def test_resolve_rate_limit_uses_roe_value(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _write_roe(
        paths,
        "---\nmax_requests_per_second: 50\n---\n",
    )
    assert nuclei_scan_cli.resolve_rate_limit(paths, "hackerone", "example") == 50


def test_resolve_rate_limit_floor_when_roe_missing(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    # No roe.md written at all → conservative floor applies.
    assert nuclei_scan_cli.resolve_rate_limit(paths, "hackerone", "example") == 10


def test_resolve_rate_limit_floor_when_field_unspecified(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _write_roe(paths, "---\ndos_authorized: false\n---\n")
    assert nuclei_scan_cli.resolve_rate_limit(paths, "hackerone", "example") == 10
