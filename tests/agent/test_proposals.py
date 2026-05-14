"""Tests for the proposals writer — slug + language whitelist + non-exec bit."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from earn_money.agent.proposals import (
    InvalidProposal,
    write_script_proposal,
    write_tool_gap_proposal,
)


def test_write_script_proposal_writes_non_executable(tmp_path: Path) -> None:
    target = write_script_proposal(
        tmp_path, slug="probe-jwt", language="py",
        body='print("hello")\n', rationale="explore jwt parsing",
    )
    assert target.is_file()
    # Executable bit is OFF by intent — operator must chmod +x after review.
    mode = target.stat().st_mode
    assert not mode & (os.X_OK), f"file is executable: oct mode {oct(mode)}"
    assert target.suffix == ".py"
    assert ".proposal." in target.name
    text = target.read_text(encoding="utf-8")
    assert "AGENT PROPOSAL — REVIEW BEFORE EXECUTING" in text
    assert 'print("hello")' in text


def test_write_script_proposal_sh_header(tmp_path: Path) -> None:
    target = write_script_proposal(
        tmp_path, slug="probe-cors", language="sh",
        body='curl -I https://example.com\n', rationale="check CORS",
    )
    text = target.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert "AGENT PROPOSAL" in text


def test_write_script_proposal_rejects_bad_slug(tmp_path: Path) -> None:
    with pytest.raises(InvalidProposal):
        write_script_proposal(
            tmp_path, slug="../../etc/passwd", language="sh",
            body="echo x", rationale="r",
        )
    with pytest.raises(InvalidProposal):
        write_script_proposal(
            tmp_path, slug="Has Capitals", language="sh",
            body="echo x", rationale="r",
        )


def test_write_script_proposal_rejects_bad_language(tmp_path: Path) -> None:
    with pytest.raises(InvalidProposal):
        write_script_proposal(
            tmp_path, slug="ok-slug", language="exe",
            body="rm -rf /", rationale="r",
        )


def test_write_tool_gap_proposal(tmp_path: Path) -> None:
    target = write_tool_gap_proposal(
        tmp_path, slug="ffuf-wrapper",
        rationale="need endpoint fuzzing", design_md="## design\nstuff",
    )
    assert target.is_file()
    assert target.suffix == ".md"
    text = target.read_text(encoding="utf-8")
    assert "ffuf-wrapper" in text
    assert "need endpoint fuzzing" in text
    assert "stuff" in text
