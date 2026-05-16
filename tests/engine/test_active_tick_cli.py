"""Tests for --hack and --roe-profile flags in active_tick_cli."""

from pathlib import Path
from unittest.mock import patch

import pytest

from earn_money.engine import active_tick_cli


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    (tmp_path / "RECON_ENABLED").touch()
    return tmp_path


class TestHackFlag:
    def test_hack_calls_hacker_loop_cli_main(self, tmp_root: Path):
        with patch("earn_money.agent.hacker_loop_cli.main") as mock_main:
            mock_main.return_value = 0
            code = active_tick_cli.main([
                "--hack", "https://target.example.com",
                "--platform", "local",
                "--program", "test",
                "--root", str(tmp_root),
            ])
        mock_main.assert_called_once()
        assert code == 0

    def test_normal_pipeline_does_not_run_when_hack_present(self, tmp_root: Path):
        with patch("earn_money.agent.hacker_loop_cli.main") as mock_main:
            mock_main.return_value = 0
            with patch("earn_money.engine.active_pipeline.run_program_pipeline") as mock_pipeline:
                active_tick_cli.main([
                    "--hack", "https://target.example.com",
                    "--platform", "local",
                    "--program", "test",
                    "--root", str(tmp_root),
                ])
        mock_pipeline.assert_not_called()

    def test_roe_profile_passed_through(self, tmp_root: Path, tmp_path: Path):
        roe_file = tmp_path / "test.yaml"
        roe_file.write_text(
            "name: t\nallowed_hosts: [x.com]\nmax_requests: 10\nmax_posts: 5\n"
            "max_turns: 5\nmax_runtime_seconds: 30\nmax_response_bytes: 1000\n"
            "delay_between_requests_ms: 0\n"
        )
        captured: list[list[str]] = []

        def _capture(argv: list[str] | None = None) -> int:
            captured.append(argv or [])
            return 0

        with patch("earn_money.agent.hacker_loop_cli.main", side_effect=_capture):
            active_tick_cli.main([
                "--hack", "https://target.example.com",
                "--platform", "local",
                "--program", "test",
                "--root", str(tmp_root),
                "--roe-profile", str(roe_file),
            ])

        assert captured
        args = captured[0]
        assert "--roe-profile" in args
        assert str(roe_file) in args

    def test_platform_program_base_url_root_passed_correctly(self, tmp_root: Path):
        captured: list[list[str]] = []

        def _capture(argv: list[str] | None = None) -> int:
            captured.append(argv or [])
            return 0

        with patch("earn_money.agent.hacker_loop_cli.main", side_effect=_capture):
            active_tick_cli.main([
                "--hack", "https://myapp.com",
                "--platform", "hackerone",
                "--program", "myapp",
                "--root", str(tmp_root),
            ])

        args = captured[0]
        assert "--platform" in args and "hackerone" in args
        assert "--program" in args and "myapp" in args
        assert "--base-url" in args and "https://myapp.com" in args
        assert "--root" in args and str(tmp_root) in args
