from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config, flags


def test_require_recon_enabled_raises_when_flag_absent(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    with pytest.raises(flags.ReconDisabled):
        flags.require_recon_enabled(paths)


def test_require_recon_enabled_passes_when_flag_present(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    flags.require_recon_enabled(paths)  # no raise


def test_program_freeze_flag_roundtrip(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    assert not flags.is_program_frozen(paths, "hackerone", "example")
    flags.freeze_program(paths, "hackerone", "example", reason="scope drift: 2 assets removed")
    assert flags.is_program_frozen(paths, "hackerone", "example")
    assert "scope drift" in flags.freeze_reason(paths, "hackerone", "example")


def test_unfreeze_program_removes_flag(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    flags.freeze_program(paths, "hackerone", "example", reason="test")
    flags.unfreeze_program(paths, "hackerone", "example")
    assert not flags.is_program_frozen(paths, "hackerone", "example")


def test_require_program_not_frozen_raises(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    flags.freeze_program(paths, "hackerone", "example", reason="dest-diff: a, b removed")
    with pytest.raises(flags.ProgramFrozen) as excinfo:
        flags.require_program_not_frozen(paths, "hackerone", "example")
    assert "dest-diff: a, b removed" in str(excinfo.value)
