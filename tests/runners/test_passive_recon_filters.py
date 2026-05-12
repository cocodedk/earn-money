"""Scope-filter + apex-extraction tests for the passive-recon runner.

Split from ``test_passive_recon.py`` to keep both files under the 200-line
project cap. These tests cover the pure helpers (`_apexes_from_in_scope`,
`_is_in_scope`) and one integration test (`test_excludes_out_of_scope_subdomains`)
that exercises the out-of-scope filter end-to-end through ``run_program``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

from earn_money import config, scope
from earn_money.runners import passive_recon
from tests.runners.test_passive_recon import _chaos_client, _seed


def test_excludes_out_of_scope_subdomains(tmp_repo: Path) -> None:
    """A FQDN that matches in_scope but also matches out_of_scope must be dropped
    before resolving + upserting. Otherwise broad wildcards can re-admit hosts
    the program explicitly excluded."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(
        paths,
        policy_value="rate-limited-OK",
        in_scope=["*.example.com"],
        out_of_scope=["blog.example.com"],
    )

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    def subfinder_run(_: str) -> list[str]:
        return ["api.example.com", "blog.example.com"]

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    assert result.subdomains_discovered == 1
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM assets").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com"]


def test_out_of_scope_wildcard_excluded() -> None:
    """Out-of-scope entries that themselves use the *.suffix wildcard form must
    still exclude every descendant FQDN."""
    assert not scope.is_in_scope(
        "auth.legacy.example.com",
        in_scope=["*.example.com"],
        out_of_scope=["*.legacy.example.com"],
    )
    assert scope.is_in_scope(
        "api.example.com",
        in_scope=["*.example.com"],
        out_of_scope=["*.legacy.example.com"],
    )


def test_private_suffix_not_collapsed_to_provider_apex() -> None:
    """An explicit S3-bucket FQDN must not collapse to amazonaws.com — handing
    that to subfinder would enumerate the entire AWS public surface and generate
    traffic mapping to every other AWS-hosted program."""
    apexes = passive_recon._apexes_from_in_scope([
        "hackerone-us-west-2-production-attachments.s3.us-west-2.amazonaws.com",
    ])
    assert "amazonaws.com" not in apexes


def test_explicit_fqdn_scope_entries_are_candidates(tmp_repo: Path) -> None:
    """Non-wildcard in_scope entries must reach the candidate set without
    relying on subfinder/chaos to surface them. Discovery tools enumerate
    *subdomains of* an apex; they do not return the apex itself, so an
    explicit literal scope entry would otherwise be silently dropped."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(
        paths,
        policy_value="rate-limited-OK",
        in_scope=[
            "example.com",
            "app.example.com",
            "bucket.s3.us-west-2.amazonaws.com",
            "*.api.example.com",
        ],
    )

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    # subfinder + chaos return nothing — only explicit literals should appear.
    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
        dns_resolver=fake_resolver,
        subfinder_run=lambda _: [],
    )

    assert result.subdomains_discovered == 3
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM assets ORDER BY subdomain").fetchall()
    conn.close()
    assert [r[0] for r in rows] == [
        "app.example.com",
        "bucket.s3.us-west-2.amazonaws.com",
        "example.com",
    ]


def test_public_suffix_apex_extraction_still_works() -> None:
    """Regression guard: ordinary domains (incl. multi-label TLDs) still collapse
    to their registrable apex when the PSL-private fix is in place."""
    apexes = passive_recon._apexes_from_in_scope([
        "api.example.com",
        "*.deep.example.co.uk",
        "hackerone.com",
        "mta-sts.wearehackerone.com",
    ])
    assert apexes == {"example.com", "example.co.uk", "hackerone.com", "wearehackerone.com"}
