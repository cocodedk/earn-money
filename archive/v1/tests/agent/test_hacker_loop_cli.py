"""Tests for hacker_loop_cli."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from earn_money.agent import hacker_loop_cli


def _base_argv(tmp_root: Path, base_url: str = "https://target.example.com") -> list[str]:
    return [
        "--platform", "local",
        "--program", "test-prog",
        "--base-url", base_url,
        "--root", str(tmp_root),
    ]


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    (tmp_path / "RECON_ENABLED").touch()
    return tmp_path


class TestHackerLoopCli:
    def test_missing_base_url_raises_system_exit(self, tmp_root: Path):
        with pytest.raises(SystemExit):
            hacker_loop_cli.main(["--platform", "local", "--program", "p"])

    def test_gate_fails_without_recon_enabled(self, tmp_path: Path):
        # no RECON_ENABLED file
        code = hacker_loop_cli.main(_base_argv(tmp_path))
        assert code == 1

    def test_missing_roe_profile_uses_safe_default(self, tmp_root: Path):
        with patch("earn_money.agent.hacker_loop_cli.HackerLoop") as MockLoop:
            mock_result = MagicMock()
            mock_result.turns = 0
            mock_result.candidate_findings = []
            mock_result.verified_findings = []
            mock_result.policy_denials = []
            mock_result.stop_reason = "done"
            MockLoop.return_value.run.return_value = mock_result
            with patch("earn_money.agent.hacker_loop_cli.providers_mod.from_env"):
                code = hacker_loop_cli.main(_base_argv(tmp_root))
        assert code == 0

    def test_custom_roe_profile_loads(self, tmp_root: Path, tmp_path: Path):
        yaml_content = (
            "name: test-roe\n"
            "allowed_hosts: [target.example.com]\n"
            "max_requests: 50\n"
            "max_posts: 10\n"
            "max_turns: 5\n"
            "max_runtime_seconds: 60\n"
            "max_response_bytes: 1000\n"
            "delay_between_requests_ms: 0\n"
        )
        roe_file = tmp_path / "test.yaml"
        roe_file.write_text(yaml_content)

        with patch("earn_money.agent.hacker_loop_cli.HackerLoop") as MockLoop:
            mock_result = MagicMock()
            mock_result.turns = 0
            mock_result.candidate_findings = []
            mock_result.verified_findings = []
            mock_result.policy_denials = []
            mock_result.stop_reason = "done"
            MockLoop.return_value.run.return_value = mock_result
            with patch("earn_money.agent.hacker_loop_cli.providers_mod.from_env"):
                code = hacker_loop_cli.main([*_base_argv(tmp_root), "--roe-profile", str(roe_file)])
        assert code == 0

    def test_cli_overrides_limits_stricter_only(self, tmp_root: Path):
        with patch("earn_money.agent.hacker_loop_cli.HackerLoop") as MockLoop:
            mock_result = MagicMock()
            mock_result.turns = 0
            mock_result.candidate_findings = []
            mock_result.verified_findings = []
            mock_result.policy_denials = []
            mock_result.stop_reason = "done"
            MockLoop.return_value.run.return_value = mock_result
            with patch("earn_money.agent.hacker_loop_cli.providers_mod.from_env"):
                hacker_loop_cli.main([*_base_argv(tmp_root), "--max-turns", "3"])
            # Budget should have max_turns <= 3
            call_args = MockLoop.call_args
            budget = call_args[0][3]  # positional: profile, roe_policy, http_tool, budget, ...
            assert budget._max_turns <= 3

    def test_cli_seeds_from_base_url_when_no_db(self, tmp_root: Path):
        with patch("earn_money.agent.hacker_loop_cli.HackerLoop") as MockLoop:
            mock_result = MagicMock()
            mock_result.turns = 0
            mock_result.candidate_findings = []
            mock_result.verified_findings = []
            mock_result.policy_denials = []
            mock_result.stop_reason = "done"
            MockLoop.return_value.run.return_value = mock_result
            with patch("earn_money.agent.hacker_loop_cli.providers_mod.from_env"):
                hacker_loop_cli.main(_base_argv(tmp_root))
            session = MockLoop.call_args[0][4]
            assert "https://target.example.com" in session.urls

    def test_cli_prints_verified_findings(self, tmp_root: Path, capsys: pytest.CaptureFixture):
        with patch("earn_money.agent.hacker_loop_cli.HackerLoop") as MockLoop:
            mock_result = MagicMock()
            mock_result.turns = 1
            mock_result.candidate_findings = []
            mock_result.verified_findings = [{"type": "idor", "path": "/api/users/999"}]
            mock_result.policy_denials = []
            mock_result.stop_reason = "done"
            MockLoop.return_value.run.return_value = mock_result
            with patch("earn_money.agent.hacker_loop_cli.providers_mod.from_env"):
                hacker_loop_cli.main(_base_argv(tmp_root))
        out = capsys.readouterr().out
        assert "[verified:idor]" in out

    def test_cli_prints_candidate_findings(self, tmp_root: Path, capsys: pytest.CaptureFixture):
        with patch("earn_money.agent.hacker_loop_cli.HackerLoop") as MockLoop:
            mock_result = MagicMock()
            mock_result.turns = 1
            mock_result.candidate_findings = [{"type": "debug_endpoint", "path": "/actuator"}]
            mock_result.verified_findings = []
            mock_result.policy_denials = []
            mock_result.stop_reason = "done"
            MockLoop.return_value.run.return_value = mock_result
            with patch("earn_money.agent.hacker_loop_cli.providers_mod.from_env"):
                hacker_loop_cli.main(_base_argv(tmp_root))
        out = capsys.readouterr().out
        assert "[candidate:debug_endpoint]" in out

    def test_cli_prints_policy_denials(self, tmp_root: Path, capsys: pytest.CaptureFixture):
        with patch("earn_money.agent.hacker_loop_cli.HackerLoop") as MockLoop:
            mock_result = MagicMock()
            mock_result.turns = 1
            mock_result.candidate_findings = []
            mock_result.verified_findings = []
            mock_result.policy_denials = ["brute force not allowed"]
            mock_result.stop_reason = "done"
            MockLoop.return_value.run.return_value = mock_result
            with patch("earn_money.agent.hacker_loop_cli.providers_mod.from_env"):
                hacker_loop_cli.main(_base_argv(tmp_root))
        out = capsys.readouterr().out
        assert "[denied]" in out

    def test_cli_returns_zero_on_success(self, tmp_root: Path):
        with patch("earn_money.agent.hacker_loop_cli.HackerLoop") as MockLoop:
            mock_result = MagicMock()
            mock_result.turns = 0
            mock_result.candidate_findings = []
            mock_result.verified_findings = []
            mock_result.policy_denials = []
            mock_result.stop_reason = "done"
            MockLoop.return_value.run.return_value = mock_result
            with patch("earn_money.agent.hacker_loop_cli.providers_mod.from_env"):
                code = hacker_loop_cli.main(_base_argv(tmp_root))
        assert code == 0
