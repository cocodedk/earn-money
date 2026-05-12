from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from earn_money.recon import subfinder


def test_runs_subfinder_with_expected_args(
    fixtures_dir: Path, mocker: pytest.MonkeyPatch
) -> None:
    output = (fixtures_dir / "subfinder_output.txt").read_text(encoding="utf-8")
    mock_run = mocker.patch(
        "earn_money.recon.subfinder.subprocess.run",
        return_value=MagicMock(stdout=output, returncode=0, stderr=""),
    )

    result = subfinder.enumerate_subdomains("example.com")

    assert sorted(result) == [
        "api.example.com",
        "internal.example.com",
        "mail.example.com",
        "www.example.com",
    ]
    args, kwargs = mock_run.call_args
    assert args[0] == ["subfinder", "-d", "example.com", "-silent", "-all"]
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def test_returns_empty_list_on_no_output(mocker: pytest.MonkeyPatch) -> None:
    mocker.patch(
        "earn_money.recon.subfinder.subprocess.run",
        return_value=MagicMock(stdout="", returncode=0, stderr=""),
    )
    assert subfinder.enumerate_subdomains("example.com") == []


def test_subprocess_failure_raises(mocker: pytest.MonkeyPatch) -> None:
    mocker.patch(
        "earn_money.recon.subfinder.subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd="subfinder", stderr="boom"
        ),
    )
    with pytest.raises(subfinder.SubfinderError):
        subfinder.enumerate_subdomains("example.com")


def test_missing_binary_raises(mocker: pytest.MonkeyPatch) -> None:
    mocker.patch(
        "earn_money.recon.subfinder.subprocess.run",
        side_effect=FileNotFoundError("subfinder"),
    )
    with pytest.raises(subfinder.SubfinderError):
        subfinder.enumerate_subdomains("example.com")
