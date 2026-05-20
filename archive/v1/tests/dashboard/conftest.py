"""Shared fixtures for dashboard probe-runner + probe-route tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from earn_money import config


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    (tmp_path / "RECON_ENABLED").touch()
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_probe_slot():
    """Ensure no probe slot leaks between tests. The handler installs
    a _FakeRunner under server._PROBE_SLOT on a successful start; without
    this fixture a subsequent test would see a stale 409 from a slot the
    previous test left in place."""
    from earn_money.dashboard import server
    server._PROBE_SLOT = None
    yield
    server._PROBE_SLOT = None


@pytest.fixture()
def handler_factory(tmp_root: Path):
    from earn_money.dashboard import server

    from ._probe_routes_helpers import _FakeRunner

    paths = config.Paths.from_root(tmp_root)
    # Patch ProbeRunner in the server module to our fake.
    with patch.object(server, "ProbeRunner", _FakeRunner, create=True):
        index_html = b"<!doctype html><title>t</title>"
        static = {}
        yield server._make_handler(paths, index_html, static), paths


@pytest.fixture()
def make_runner(tmp_path, monkeypatch):
    """Build a real ProbeRunner instance without starting its thread.

    Returns a factory that accepts canned LLM-reply strings (in order)
    and optional profile overrides. The factory bypasses the real
    OpenRouter provider and resolves RoE paths under tmp_path/roe."""

    def _factory(replies, *, presolved: bool = True, **profile_overrides):
        from earn_money import config
        from earn_money.agent.action_classes import ActionClass
        from earn_money.dashboard import probe_runner as pr

        (tmp_path / "RECON_ENABLED").touch()
        roe_dir = tmp_path / "roe"
        roe_dir.mkdir(exist_ok=True)
        roe_yaml = roe_dir / "test.yaml"
        roe_yaml.write_text(
            "name: test\n"
            "allowed_hosts: [target.example.com]\n"
            "max_requests: 100\nmax_posts: 20\nmax_turns: 10\n"
            "max_runtime_seconds: 60\nmax_response_bytes: 5000\n"
            "delay_between_requests_ms: 0\n"
            "allow_get: true\nallow_post: true\nallow_idor_checks: true\n",
        )

        provider = MagicMock()
        iter_replies = iter(replies)
        provider.complete.side_effect = lambda **_kw: next(iter_replies)
        monkeypatch.setattr(
            "earn_money.dashboard.probe_runner.providers_mod.from_env",
            lambda: provider,
        )

        paths = config.Paths.from_root(tmp_path)
        runner = pr.ProbeRunner(
            base_url="https://target.example.com",
            roe_path=roe_yaml,
            paths=paths,
            target_kind="local_lab",
        )
        if presolved:
            # Pre-mark all probe classes as tried so single-STOP fixtures
            # are still valid under the new STOP-validation rule. Tests
            # that exercise STOP escalation pass `presolved=False`.
            runner.session.tried_action_classes = set(ActionClass)
        return runner

    return _factory
