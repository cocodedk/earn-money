from __future__ import annotations

from pathlib import Path

from earn_money.recon import httpx_tool


def test_parse_jsonl_returns_services(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "httpx_output.jsonl").read_text(encoding="utf-8")
    services = httpx_tool.parse_jsonl(raw, run_id="r1", observed_at="t1")
    assert len(services) == 2
    api = services[0]
    assert api.subdomain == "api.example.com"
    assert api.scheme == "https"
    assert api.port == 443
    assert api.status_code == 200
    assert api.title == "Example API"
    assert api.server == "nginx"
    assert tuple(api.technologies) == ("nginx", "openresty")
    assert api.redirect_to is None
    assert api.tls_summary is not None


def test_parse_jsonl_captures_redirect_target(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "httpx_output.jsonl").read_text(encoding="utf-8")
    services = httpx_tool.parse_jsonl(raw, run_id="r1", observed_at="t1")
    www = services[1]
    assert www.redirect_to == "https://www.example.com/"
    assert www.status_code == 301


def test_command_includes_safety_flags() -> None:
    cmd = httpx_tool.build_command(["api.example.com", "www.example.com"])
    assert "-no-follow-redirects" in cmd
    assert "-json" in cmd
    assert "-silent" in cmd
    # Targets are passed via -u with comma separation.
    u_index = cmd.index("-u")
    assert cmd[u_index + 1] == "api.example.com,www.example.com"


def test_command_requires_at_least_one_target() -> None:
    import pytest
    with pytest.raises(ValueError, match="at least one target"):
        httpx_tool.build_command([])


def test_parse_skips_malformed_lines(fixtures_dir: Path) -> None:
    raw = "not-json\n" + (fixtures_dir / "httpx_output.jsonl").read_text(encoding="utf-8")
    services = httpx_tool.parse_jsonl(raw, run_id="r1", observed_at="t1")
    # The "not-json" line is skipped; the two real lines remain.
    assert len(services) == 2
