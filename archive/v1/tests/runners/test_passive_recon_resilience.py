"""Source-failure resilience for the passive-recon runner.

A cron-driven recon pipeline must keep running when any single external
source (subfinder, chaos, ...) fails for any single apex. Failures should
be logged and counted, not propagated as fatals — otherwise one flaky API
call discards every other source's data for the whole run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import httpx

from earn_money import config
from earn_money.recon import chaos, subfinder
from earn_money.runners import passive_recon
from tests.runners.test_passive_recon import _seed


def _chaos_error_client() -> chaos.Client:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"valid": False, "message": "internal ratelimit server error"},
        )
    return chaos.Client(token="t", transport=httpx.MockTransport(handler))


def test_continues_when_chaos_fails(tmp_repo: Path, capsys) -> None:
    """Chaos returning 500 mid-run must not discard subfinder data — the run
    finishes with subfinder-only output and the failure is logged."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    def subfinder_run(_: str) -> list[str]:
        return ["api.example.com", "www.example.com"]

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=_chaos_error_client(),
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    assert result.subdomains_discovered == 2
    assert result.source_failures == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM assets ORDER BY subdomain").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com", "www.example.com"]

    err = capsys.readouterr().err
    assert "chaos" in err.lower()
    assert "example.com" in err


def test_continues_when_subfinder_fails(tmp_repo: Path, capsys) -> None:
    """Subfinder failing (e.g. timeout, missing binary) must not discard
    Chaos data — the run finishes with chaos-only output and the failure
    is logged."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"domain": "example.com", "subdomains": ["api"]}
        )
    chaos_client = chaos.Client(token="t", transport=httpx.MockTransport(handler))

    def subfinder_run(_: str) -> list[str]:
        raise subfinder.SubfinderError("subfinder timed out after 300s for example.com")

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=chaos_client,
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    assert result.subdomains_discovered == 1
    assert result.source_failures == 1
    err = capsys.readouterr().err
    assert "subfinder" in err.lower()


def test_clean_run_reports_zero_source_failures(tmp_repo: Path) -> None:
    """Regression: a fully successful run still surfaces source_failures=0
    so monitors can rely on the field being present every run."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"domain": "example.com", "subdomains": []}
        )
    chaos_client = chaos.Client(token="t", transport=httpx.MockTransport(handler))

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=chaos_client,
        dns_resolver=fake_resolver,
        subfinder_run=lambda _: ["api.example.com"],
    )

    assert result.source_failures == 0
