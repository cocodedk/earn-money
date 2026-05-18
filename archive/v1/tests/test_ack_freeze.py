"""Tests for bin/ack-freeze shell helper.

Tests use ACK_FREEZE_ROOT to redirect the script's ROOT at a tmp_path, so
no test ever writes to the real `programs/` tree. The binary itself lives
in _REPO_ROOT (we can't move that) but all program data is in tmp_path.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[1].resolve()
_ACK_FREEZE = _REPO_ROOT / "bin" / "ack-freeze"


def _run(
    args: list[str],
    root: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run bin/ack-freeze with ROOT redirected to `root` via ACK_FREEZE_ROOT."""
    env = {**os.environ, "ACK_FREEZE_ROOT": str(root)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(_ACK_FREEZE), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _seed_program(root: Path, platform: str, slug: str) -> Path:
    """Create scope.md under `root` so the program is considered registered."""
    prog_dir = root / "programs" / platform / slug
    prog_dir.mkdir(parents=True, exist_ok=True)
    (prog_dir / "scope.md").write_text(
        f"---\nplatform: {platform}\nslug: {slug}\npolicy: rate-limited-OK\n"
        "in_scope:\n  - '*.example.com'\nout_of_scope: []\n"
        "scope_hash: seed\nlast_synced: '2026-05-12'\n---\n",
        encoding="utf-8",
    )
    return prog_dir


def _write_editor(tmp_path: Path, body: str, name: str = "_test_editor.sh") -> Path:
    """Stub $EDITOR that writes `body` to its argument file."""
    script = tmp_path / name
    script.write_text(f"#!/bin/sh\nprintf '%s' {body!r} > \"$1\"\n", encoding="utf-8")
    script.chmod(0o755)
    return script


def test_refuses_no_args(tmp_path: Path) -> None:
    result = _run([], tmp_path)
    assert result.returncode != 0
    assert "usage" in result.stderr.lower()


def test_refuses_bad_arg_format(tmp_path: Path) -> None:
    result = _run(["nosep"], tmp_path)
    assert result.returncode != 0
    assert "platform" in result.stderr.lower() or "usage" in result.stderr.lower()


def test_refuses_path_traversal(tmp_path: Path) -> None:
    """Reject `..`, leading `/`, double `//`."""
    for bad in ["../etc/passwd", "/abs/path", "a//b", "../../foo"]:
        result = _run([bad], tmp_path)
        assert result.returncode != 0, f"accepted: {bad}"
        assert "invalid program path" in result.stderr or "must be" in result.stderr


def test_refuses_missing_frozen_flag(tmp_path: Path) -> None:
    _seed_program(tmp_path, "hackerone", "demo")
    result = _run(["hackerone/demo"], tmp_path)
    assert result.returncode != 0
    assert "FROZEN" in result.stderr


def test_refuses_unregistered_program(tmp_path: Path) -> None:
    result = _run(["hackerone/ghost"], tmp_path)
    assert result.returncode != 0
    assert "not registered" in result.stderr


def test_success_appends_audit_and_removes_frozen(tmp_path: Path) -> None:
    """Happy path: FROZEN exists + scope.md exists + non-empty reason."""
    prog_dir = _seed_program(tmp_path, "hackerone", "demo")
    frozen = prog_dir / "FROZEN"
    log = prog_dir / "freeze-acks.log"

    frozen.write_text(
        "scope removed api.example.com at 2026-05-12T10:00:00Z\n",
        encoding="utf-8",
    )
    editor = _write_editor(tmp_path, "Rescoped; asset re-added by program owner.")

    result = _run(["hackerone/demo"], tmp_path, extra_env={"EDITOR": str(editor)})

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert not frozen.exists(), "FROZEN flag should have been removed"
    assert log.exists()
    content = log.read_text(encoding="utf-8")
    assert "Rescoped" in content
    assert "frozen-content-was:" in content


def test_refuses_empty_reason(tmp_path: Path) -> None:
    """Editor that writes only comments → empty reason → reject; keep FROZEN."""
    prog_dir = _seed_program(tmp_path, "hackerone", "demo")
    frozen = prog_dir / "FROZEN"
    frozen.write_text("some diff\n", encoding="utf-8")

    editor = _write_editor(tmp_path, "# just a comment\n", name="_test_editor_empty.sh")
    result = _run(["hackerone/demo"], tmp_path, extra_env={"EDITOR": str(editor)})

    assert result.returncode != 0
    assert "empty reason" in result.stderr
    assert frozen.exists(), "FROZEN must remain on failure"
