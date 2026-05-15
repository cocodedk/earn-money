"""Regression tests for scope-sync non-HackerOne platform guard."""
from __future__ import annotations

from pathlib import Path

from earn_money import config, flags
from earn_money.runners import scope_sync


def test_non_hackerone_platform_exits_zero_no_freeze(tmp_path: Path) -> None:
    """scope-sync must exit 0 and never write FROZEN for unknown platforms."""
    root = tmp_path
    paths = config.Paths.from_root(root)
    paths.recon_enabled_flag.touch()
    prog_dir = root / "programs" / "local" / "juice-shop"
    prog_dir.mkdir(parents=True)
    (prog_dir / "scope.md").write_text("policy: rate-limited-OK\nin_scope:\n  - target.cocode.dk\n")

    rc = scope_sync.main(["--platform", "local", "--program", "juice-shop", "--root", str(root)])

    assert rc == 0
    assert not flags.is_program_frozen(paths, "local", "juice-shop")


def test_non_hackerone_skips_before_env_check(tmp_path: Path) -> None:
    """Skip fires even without HACKERONE_API_USERNAME/TOKEN set."""
    root = tmp_path
    paths = config.Paths.from_root(root)
    # No RECON_ENABLED, no H1 creds — still returns 0
    rc = scope_sync.main(["--platform", "ctf", "--program", "any", "--root", str(root)])
    assert rc == 0
    assert not flags.is_program_frozen(paths, "ctf", "any")
