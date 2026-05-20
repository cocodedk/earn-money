"""Contract tests for `apps.programs.preflight`.

Coverage matrix per [[plan slice D]]:
- URL normalisation: http/https only, hostless URLs rejected, IDNA.
- `preflight_scan_run` raises the right narrow exception per failure:
  OutOfScope / AmbiguousProgram / ManualOnly / AmbiguousPolicy /
  ReconDisabled / ProgramFrozen.
- In-scope target with passing checks returns the resolved Program.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from django.test import override_settings

from apps.programs.exceptions import (
    AmbiguousPolicy,
    AmbiguousProgram,
    ManualOnly,
    OutOfScope,
    ProgramFrozen,
    ReconDisabled,
)
from apps.programs.preflight import host_from_url, preflight_scan_run


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _seed(root: Path, slug: str, *, policy: str = "rate-limited-OK",
          in_scope: list[str] | None = None) -> None:
    in_scope = in_scope if in_scope is not None else ["www.algolia.com"]
    # Quote each entry to dodge YAML's `*` alias-prefix gotcha on wildcards.
    in_scope_lines = "\n".join(f'        - "{entry}"' for entry in in_scope)
    _write(root / "hackerone" / slug / "scope.md", f"""
        ---
        platform: hackerone
        slug: {slug}
        policy: {policy}
        in_scope:
{in_scope_lines}
        out_of_scope: []
        ---
    """)
    _write(root / "hackerone" / slug / "roe.md", """
        ---
        max_requests_per_second: 10
        ---
    """)


# --- host_from_url ---


def test_host_from_url_http() -> None:
    assert host_from_url("http://www.algolia.com/path") == "www.algolia.com"


def test_host_from_url_https() -> None:
    assert host_from_url("https://www.algolia.com:443/x") == "www.algolia.com"


def test_host_from_url_rejects_empty() -> None:
    with pytest.raises(ValueError):
        host_from_url("")


def test_host_from_url_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError, match="scheme must be one of"):
        host_from_url("ftp://www.algolia.com/")


def test_host_from_url_rejects_hostless() -> None:
    with pytest.raises(ValueError, match="no hostname"):
        host_from_url("https:///just/a/path")


def test_host_from_url_idna_normalises() -> None:
    # IDNA-encodes unicode; lower-cases.
    assert host_from_url("https://Algoliá.com/") == "xn--algoli-uta.com"


def _enable_recon(tmp_path: Path) -> Path:
    flag = tmp_path / "RECON_ENABLED"
    flag.write_text("on", encoding="utf-8")
    return flag


# --- preflight_scan_run happy path ---


def test_preflight_returns_programs_when_all_checks_pass(tmp_path: Path) -> None:
    flag = _enable_recon(tmp_path)
    progs_root = tmp_path / "programs"
    _seed(progs_root, "algolia")
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        from apps.programs import loader
        loader._default_registry = None  # force fresh cache for the override
        programs = preflight_scan_run(["https://www.algolia.com"])
    assert len(programs) == 1
    assert programs[0].slug == "algolia"


# --- preflight refuse cases ---


def test_preflight_raises_recon_disabled_when_flag_missing(tmp_path: Path) -> None:
    progs_root = tmp_path / "programs"
    _seed(progs_root, "algolia")
    missing_flag = tmp_path / "no-flag"
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=missing_flag):
        with pytest.raises(ReconDisabled):
            preflight_scan_run(["https://www.algolia.com"])


def test_preflight_raises_out_of_scope_for_unknown_host(tmp_path: Path) -> None:
    flag = _enable_recon(tmp_path)
    progs_root = tmp_path / "programs"
    _seed(progs_root, "algolia")
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        from apps.programs import loader
        loader._default_registry = None
        with pytest.raises(OutOfScope):
            preflight_scan_run(["https://evil.example.com"])


def test_preflight_raises_manual_only(tmp_path: Path) -> None:
    flag = _enable_recon(tmp_path)
    progs_root = tmp_path / "programs"
    _seed(progs_root, "manual-prog", policy="manual-only",
          in_scope=["manual.example.com"])
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        from apps.programs import loader
        loader._default_registry = None
        with pytest.raises(ManualOnly):
            preflight_scan_run(["https://manual.example.com"])


def test_preflight_raises_ambiguous_policy_for_active_stub(tmp_path: Path) -> None:
    flag = _enable_recon(tmp_path)
    progs_root = tmp_path / "programs"
    _seed(progs_root, "amb-prog", policy="ambiguous",
          in_scope=["amb.example.com"])
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        from apps.programs import loader
        loader._default_registry = None
        with pytest.raises(AmbiguousPolicy):
            preflight_scan_run(["https://amb.example.com"], active=True)


def test_preflight_passive_allows_ambiguous_policy(tmp_path: Path) -> None:
    """Passive-recon runners can target `ambiguous` programs — they
    don't issue active probes, so they're allowed."""
    flag = _enable_recon(tmp_path)
    progs_root = tmp_path / "programs"
    _seed(progs_root, "amb-prog", policy="ambiguous",
          in_scope=["amb.example.com"])
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        from apps.programs import loader
        loader._default_registry = None
        programs = preflight_scan_run(["https://amb.example.com"], active=False)
    assert programs[0].slug == "amb-prog"


def test_preflight_raises_program_frozen(tmp_path: Path) -> None:
    flag = _enable_recon(tmp_path)
    progs_root = tmp_path / "programs"
    _seed(progs_root, "algolia")
    # Add the FROZEN flag.
    (progs_root / "hackerone" / "algolia" / "FROZEN").write_text(
        "destructive diff detected", encoding="utf-8",
    )
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        from apps.programs import loader
        loader._default_registry = None
        with pytest.raises(ProgramFrozen):
            preflight_scan_run(["https://www.algolia.com"])


def test_preflight_raises_ambiguous_program(tmp_path: Path) -> None:
    flag = _enable_recon(tmp_path)
    progs_root = tmp_path / "programs"
    _seed(progs_root, "a", in_scope=["*.shared.com"])
    _seed(progs_root, "b", in_scope=["*.shared.com"])
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        from apps.programs import loader
        loader._default_registry = None
        with pytest.raises(AmbiguousProgram):
            preflight_scan_run(["https://x.shared.com"])


def test_preflight_checks_every_target(tmp_path: Path) -> None:
    """A scan with one in-scope + one out-of-scope target fails on the
    second URL — no partial pass."""
    flag = _enable_recon(tmp_path)
    progs_root = tmp_path / "programs"
    _seed(progs_root, "algolia")
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        from apps.programs import loader
        loader._default_registry = None
        with pytest.raises(OutOfScope):
            preflight_scan_run([
                "https://www.algolia.com",
                "https://evil.example.com",
            ])
