"""Tests for bin/ack-freeze shell helper."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# The binary lives in the real repo, but we run it against a tmp data root.
_REPO_ROOT = Path(__file__).parents[1].resolve()
_ACK_FREEZE = _REPO_ROOT / "bin" / "ack-freeze"


def _run(
    args: list[str],
    data_root: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run bin/ack-freeze from the real repo against a temp data_root."""
    env = {**os.environ}
    # Override HOME so the script resolves ROOT relative to the binary, not cwd.
    # The script computes ROOT from dirname($0)/.. which is _REPO_ROOT.
    # We use a separate tmp dir for program data by passing the programs path.
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(_ACK_FREEZE), *args],
        capture_output=True,
        text=True,
        cwd=str(data_root),
        env=env,
    )


def _seed_program(data_root: Path, platform: str, slug: str) -> Path:
    """Create scope.md in the REAL repo so the program is considered registered."""
    prog_dir = _REPO_ROOT / "programs" / platform / slug
    prog_dir.mkdir(parents=True, exist_ok=True)
    scope = prog_dir / "scope.md"
    if not scope.exists():
        scope.write_text(
            f"---\nplatform: {platform}\nslug: {slug}\npolicy: rate-limited-OK\n"
            "in_scope:\n  - '*.example.com'\nout_of_scope: []\n"
            "scope_hash: seed\nlast_synced: '2026-05-12'\n---\n",
            encoding="utf-8",
        )
    return prog_dir


def test_refuses_no_args(tmp_path: Path) -> None:
    """Running with no arguments must print usage and exit non-zero."""
    result = _run([], tmp_path)
    assert result.returncode != 0
    assert "usage" in result.stderr.lower()


def test_refuses_bad_arg_format(tmp_path: Path) -> None:
    """Argument without a slash must print usage and exit non-zero."""
    result = _run(["nosep"], tmp_path)
    assert result.returncode != 0
    assert "platform" in result.stderr.lower() or "usage" in result.stderr.lower()


def test_refuses_missing_frozen_flag(tmp_path: Path) -> None:
    """Registered program without a FROZEN file must exit non-zero."""
    _seed_program(tmp_path, "hackerone", "security")
    # security program exists in real repo but has no FROZEN flag
    result = _run(["hackerone/security"], tmp_path)
    assert result.returncode != 0
    assert "FROZEN" in result.stderr


def test_refuses_unregistered_program_slash_arg(tmp_path: Path) -> None:
    """A program with no scope.md (slash form) must be rejected."""
    result = _run(["hackerone/ghost-program-zzz"], tmp_path)
    assert result.returncode != 0
    assert "not registered" in result.stderr


def test_success_appends_audit_and_removes_frozen(tmp_path: Path) -> None:
    """Happy path: FROZEN exists + scope.md exists + non-empty reason."""
    prog_dir = _REPO_ROOT / "programs" / "hackerone" / "security"
    frozen = prog_dir / "FROZEN"
    log = prog_dir / "freeze-acks.log"

    # Create FROZEN; remove it and the log after the test regardless
    frozen.write_text(
        "scope removed api.example.com at 2026-05-12T10:00:00Z\n",
        encoding="utf-8",
    )
    try:
        # Use a wrapper script as EDITOR that writes a reason to the temp file
        editor_script = tmp_path / "_test_editor.sh"
        editor_script.write_text(
            '#!/bin/sh\necho "Rescoped; asset re-added by program owner." > "$1"\n',
            encoding="utf-8",
        )
        editor_script.chmod(0o755)

        result = _run(
            ["hackerone/security"],
            tmp_path,
            extra_env={"EDITOR": str(editor_script)},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert not frozen.exists(), "FROZEN flag should have been removed"

        assert log.exists(), "freeze-acks.log should have been created"
        content = log.read_text(encoding="utf-8")
        assert "Rescoped" in content
        assert "frozen-content-was:" in content
    finally:
        # Clean up side-effects on the real repo
        if frozen.exists():
            frozen.unlink()
        if log.exists():
            log.unlink()


def test_refuses_empty_reason(tmp_path: Path) -> None:
    """Editor that writes only comments produces empty reason — must be rejected."""
    prog_dir = _REPO_ROOT / "programs" / "hackerone" / "security"
    frozen = prog_dir / "FROZEN"
    log = prog_dir / "freeze-acks.log"

    frozen.write_text("some diff\n", encoding="utf-8")
    try:
        # EDITOR writes nothing (all lines start with #, so after stripping = empty)
        editor_script = tmp_path / "_test_editor_empty.sh"
        editor_script.write_text(
            '#!/bin/sh\necho "# just a comment" > "$1"\n',
            encoding="utf-8",
        )
        editor_script.chmod(0o755)

        result = _run(
            ["hackerone/security"],
            tmp_path,
            extra_env={"EDITOR": str(editor_script)},
        )
        assert result.returncode != 0
        assert "empty reason" in result.stderr
        # FROZEN must still exist (not removed on failure)
        assert frozen.exists()
    finally:
        if frozen.exists():
            frozen.unlink()
        if log.exists():
            log.unlink()
