"""Tests for katana_tool — command builder + JSONL parser + scope filter."""

from __future__ import annotations

from pathlib import Path

import pytest

from earn_money.recon import katana_tool


def test_build_command_lists_targets_file() -> None:
    cmd = katana_tool.build_command("/tmp/seeds.txt", rate_limit=10)
    assert cmd[0] == "katana"
    assert cmd[cmd.index("-list") + 1] == "/tmp/seeds.txt"


def test_build_command_uses_rate_limit_and_depth() -> None:
    cmd = katana_tool.build_command(
        "/tmp/s.txt", rate_limit=50, depth=3, concurrency=20,
    )
    assert cmd[cmd.index("-rate-limit") + 1] == "50"
    assert cmd[cmd.index("-depth") + 1] == "3"
    assert cmd[cmd.index("-concurrency") + 1] == "20"


def test_build_command_includes_jsonl_and_silent() -> None:
    cmd = katana_tool.build_command("/tmp/s.txt", rate_limit=10)
    assert "-jsonl" in cmd
    assert "-silent" in cmd


def test_build_command_rejects_non_positive_rate_limit() -> None:
    with pytest.raises(ValueError):
        katana_tool.build_command("/tmp/s.txt", rate_limit=0)


def test_build_command_rejects_non_positive_depth() -> None:
    with pytest.raises(ValueError):
        katana_tool.build_command("/tmp/s.txt", rate_limit=10, depth=0)


def test_build_command_rejects_non_positive_concurrency() -> None:
    with pytest.raises(ValueError):
        katana_tool.build_command("/tmp/s.txt", rate_limit=10, concurrency=0)


def test_parse_jsonl_returns_one_record_per_line(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "katana_output.jsonl").read_text(encoding="utf-8")
    urls = katana_tool.parse_jsonl(raw)
    assert len(urls) == 3
    assert urls[0].url == "https://app.example.com/admin"
    assert urls[0].status_code == 200
    assert urls[0].method == "GET"
    assert urls[0].content_type == "text/html"


def test_parse_jsonl_skips_malformed_lines() -> None:
    raw = "not json\n{}\n" + (
        '{"request":{"method":"GET","endpoint":"https://x/"},"response":{"status_code":200}}\n'
    )
    urls = katana_tool.parse_jsonl(raw)
    assert len(urls) == 1
    assert urls[0].url == "https://x/"


def test_parse_jsonl_falls_back_to_legacy_url_field() -> None:
    raw = '{"url":"https://legacy.example.com/path"}\n'
    urls = katana_tool.parse_jsonl(raw)
    assert urls[0].url == "https://legacy.example.com/path"
    assert urls[0].status_code is None


def test_filter_in_scope_drops_oos_hosts(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "katana_output.jsonl").read_text(encoding="utf-8")
    urls = katana_tool.parse_jsonl(raw)
    keep, drops = katana_tool.filter_in_scope(
        urls, in_scope_host=lambda h: h.endswith("example.com"),
    )
    assert drops == 1
    assert all(u.url.endswith(".example.com" + u.url.split("example.com", 1)[1])
               for u in keep)
    assert "attacker.com" not in {u.url for u in keep}


def test_filter_in_scope_empty_input() -> None:
    keep, _drops = katana_tool.filter_in_scope(
        [], in_scope_host=lambda _h: True,
    )
    assert keep == []


def test_build_command_adds_cs_flags_for_crawl_scope() -> None:
    cmd = katana_tool.build_command(
        "/tmp/s.txt", rate_limit=10,
        crawl_scope=["target.cocode.dk", "api.example.com"],
    )
    cs_flags = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-cs"]
    # Dots are escaped for Katana's Go regex -cs flag
    assert cs_flags == [r"target\.cocode\.dk", r"api\.example\.com"]


def test_build_command_escapes_wildcard_in_crawl_scope() -> None:
    cmd = katana_tool.build_command(
        "/tmp/s.txt", rate_limit=10,
        crawl_scope=["*.example.com"],
    )
    cs_flags = [cmd[i + 1] for i, v in enumerate(cmd) if v == "-cs"]
    assert cs_flags == [r".*\.example\.com"]


def test_build_command_no_cs_flags_when_scope_empty() -> None:
    cmd = katana_tool.build_command("/tmp/s.txt", rate_limit=10)
    assert "-cs" not in cmd
