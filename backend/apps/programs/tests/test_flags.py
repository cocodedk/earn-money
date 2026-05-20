"""Contract tests for `apps.programs.flags`.

Coverage matrix per [[plan slice B]]:
- `require_recon_enabled()` raises `ReconDisabled` when the flag path is
  absent / is a directory; returns None when the path is a regular file.
- `is_program_frozen(platform, slug)` returns True iff
  `<PROGRAMS_ROOT>/<platform>/<slug>/FROZEN` exists.
- Both functions read their default paths from Django settings so
  containers can mount `/flags/RECON_ENABLED` while tests inject
  `tmp_path` via `override_settings`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from django.test import override_settings

from apps.programs.exceptions import ReconDisabled
from apps.programs.flags import is_program_frozen, require_recon_enabled


# --- require_recon_enabled ---


def test_require_recon_enabled_raises_when_absent(tmp_path: Path) -> None:
    """Master kill-switch: missing flag file halts the pipeline."""
    missing = tmp_path / "RECON_ENABLED"
    with pytest.raises(ReconDisabled):
        require_recon_enabled(path=missing)


def test_require_recon_enabled_raises_when_directory(tmp_path: Path) -> None:
    """Docker may create a directory when a single-file bind mount is
    missing. The flag must be a *regular file* to count as 'enabled'."""
    flag_dir = tmp_path / "RECON_ENABLED"
    flag_dir.mkdir()
    with pytest.raises(ReconDisabled):
        require_recon_enabled(path=flag_dir)


def test_require_recon_enabled_passes_when_regular_file(tmp_path: Path) -> None:
    flag = tmp_path / "RECON_ENABLED"
    flag.write_text("on", encoding="utf-8")
    # No exception — returns None.
    assert require_recon_enabled(path=flag) is None


def test_require_recon_enabled_defaults_to_settings(tmp_path: Path) -> None:
    """When no `path` is passed the function reads `RECON_ENABLED_PATH`
    from Django settings."""
    flag = tmp_path / "RECON_ENABLED"
    flag.write_text("on", encoding="utf-8")
    with override_settings(RECON_ENABLED_PATH=flag):
        assert require_recon_enabled() is None


def test_require_recon_enabled_default_raises_when_settings_path_absent(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "RECON_ENABLED"
    with override_settings(RECON_ENABLED_PATH=missing):
        with pytest.raises(ReconDisabled):
            require_recon_enabled()


def test_require_recon_enabled_error_mentions_path(tmp_path: Path) -> None:
    """Operator needs to know which path was checked when diagnosing
    a halted pipeline."""
    missing = tmp_path / "no-such-flag"
    with pytest.raises(ReconDisabled, match=str(missing)):
        require_recon_enabled(path=missing)


# --- is_program_frozen ---


def test_is_program_frozen_true_when_flag_exists(tmp_path: Path) -> None:
    program_dir = tmp_path / "hackerone" / "algolia"
    program_dir.mkdir(parents=True)
    (program_dir / "FROZEN").write_text("destructive diff\n", encoding="utf-8")
    with override_settings(PROGRAMS_ROOT=tmp_path):
        assert is_program_frozen("hackerone", "algolia") is True


def test_is_program_frozen_false_when_flag_absent(tmp_path: Path) -> None:
    program_dir = tmp_path / "hackerone" / "algolia"
    program_dir.mkdir(parents=True)
    with override_settings(PROGRAMS_ROOT=tmp_path):
        assert is_program_frozen("hackerone", "algolia") is False


def test_is_program_frozen_false_when_program_dir_absent(tmp_path: Path) -> None:
    with override_settings(PROGRAMS_ROOT=tmp_path):
        assert is_program_frozen("hackerone", "ghost-program") is False


def test_is_program_frozen_false_when_flag_is_directory(tmp_path: Path) -> None:
    """Defence-in-depth: a directory named `FROZEN` does NOT count as
    a freeze — symmetric with the RECON_ENABLED rule."""
    program_dir = tmp_path / "hackerone" / "algolia"
    program_dir.mkdir(parents=True)
    (program_dir / "FROZEN").mkdir()
    with override_settings(PROGRAMS_ROOT=tmp_path):
        assert is_program_frozen("hackerone", "algolia") is False
