"""Tests for `nuclei_scan_cli.resolve_rate_limit` — the bridge between
`roe.md` and the nuclei `-rl` flag — and the CLI's controlled-failure
exit code when `roe.md` is invalid."""

from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, roe
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


def test_resolve_rate_limit_raises_on_invalid_roe(tmp_repo: Path) -> None:
    """A semantically invalid roe.md (max_requests_per_second=0) must
    raise InvalidRoE rather than silently fall back to the floor."""
    paths = config.Paths.from_root(tmp_repo)
    _write_roe(paths, "---\nmax_requests_per_second: 0\n---\n")
    with pytest.raises(roe.InvalidRoE):
        nuclei_scan_cli.resolve_rate_limit(paths, "hackerone", "example")


def test_nuclei_scan_cli_returns_6_on_invalid_roe(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """End-to-end: malformed roe.md surfaces as controlled exit 6 with
    a named-error message, not the generic exit-1 'unexpected error'
    path. Same shape as ReconDisabled (2), ProgramFrozen (3),
    PolicyViolation (4), UnsafeTemplateProfile (5)."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _write_roe(paths, "---\nmax_requests_per_second: -1\n---\n")
    # Bare scope file so the runner advances past the policy gate.
    paths.scope_file("hackerone", "example").write_text(
        "---\nplatform: hackerone\nslug: example\npolicy: rate-limited-OK\n"
        "in_scope: [api.example.com]\nout_of_scope: []\nnotes: ''\n"
        "scope_hash: seed\nlast_synced: '2026-05-12T07:00:00Z'\n---\n",
        encoding="utf-8",
    )
    rc = nuclei_scan_cli.main(
        ["--platform", "hackerone", "--program", "example",
         "--root", str(paths.root)]
    )
    assert rc == 6
    err = capsys.readouterr().err
    assert "invalid roe.md" in err
