from __future__ import annotations

from pathlib import Path

from earn_money import config


def test_default_root_is_cwd(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    assert paths.root == tmp_repo
    assert paths.programs == tmp_repo / "programs"
    assert paths.recon_outputs == tmp_repo / "recon" / "outputs"
    assert paths.recon_enabled_flag == tmp_repo / "RECON_ENABLED"


def test_program_dir_layout(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    program_dir = paths.program_dir("hackerone", "example")
    assert program_dir == tmp_repo / "programs" / "hackerone" / "example"
    assert paths.scope_file("hackerone", "example") == program_dir / "scope.md"
    assert paths.freeze_flag("hackerone", "example") == program_dir / "FROZEN"
    assert paths.program_db("hackerone", "example") == program_dir / "db.sqlite"
