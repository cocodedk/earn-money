from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from earn_money import config, flags, policy, scope
from earn_money.recon import chaos
from earn_money.runners import passive_recon


def _seed(paths: config.Paths, *, policy_value: scope.Policy, in_scope: list[str]) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope, out_of_scope=[], notes="",
        scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _chaos_client(payload: dict) -> chaos.Client:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)
    return chaos.Client(token="t", transport=httpx.MockTransport(handler))


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])
    with pytest.raises(flags.ReconDisabled):
        passive_recon.run_program(
            paths, "hackerone", "example",
            chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
            dns_resolver=MagicMock(),
            subfinder_run=lambda d: [],
        )


def test_refuses_manual_only_policy(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="manual-only", in_scope=["*.example.com"])
    with pytest.raises(policy.PolicyViolation):
        passive_recon.run_program(
            paths, "hackerone", "example",
            chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
            dns_resolver=MagicMock(),
            subfinder_run=lambda d: [],
        )


def test_refuses_when_program_frozen(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])
    flags.freeze_program(paths, "hackerone", "example", reason="prior")
    with pytest.raises(flags.ProgramFrozen):
        passive_recon.run_program(
            paths, "hackerone", "example",
            chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
            dns_resolver=MagicMock(),
            subfinder_run=lambda d: [],
        )


def test_discovers_and_resolves_and_writes(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])

    chaos_client = _chaos_client(
        {"domain": "example.com", "subdomains": ["api", "www"]}
    )
    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = [MagicMock(address="1.2.3.4")]

    def subfinder_run(domain: str) -> list[str]:
        assert domain == "example.com"
        return ["api.example.com", "mail.example.com"]

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=chaos_client,
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    assert result.subdomains_discovered == 3  # api, www, mail (api deduped)
    assert result.assets_upserted >= 3
    import sqlite3
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain, ip FROM assets ORDER BY subdomain").fetchall()
    conn.close()
    assert sorted(r[0] for r in rows) == [
        "api.example.com", "mail.example.com", "www.example.com"
    ]
    assert all(r[1] == "1.2.3.4" for r in rows)


def test_drops_out_of_scope_subdomains(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["api.example.com"])

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    def subfinder_run(_: str) -> list[str]:
        return ["api.example.com", "other.example.com"]

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    assert result.subdomains_discovered == 1
    import sqlite3
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM assets").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com"]


def test_wildcard_match_includes_descendants(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    def subfinder_run(_: str) -> list[str]:
        return ["api.example.com", "deep.nested.example.com", "evil.com"]

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    # evil.com is out of scope.
    assert result.subdomains_discovered == 2
