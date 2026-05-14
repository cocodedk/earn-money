"""Tests for the per-program Rules of Engagement loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from earn_money.roe import InvalidRoE, RoE, default_roe, read_roe


def test_default_roe_is_conservative() -> None:
    d = default_roe()
    assert d.dos_authorized is False
    assert d.destructive_payloads_authorized is False
    assert d.social_engineering_authorized is False
    assert d.pii_handling == "one_redacted_screenshot"
    assert d.max_requests_per_second == 10
    assert d.authorized_test_environments == ()
    assert d.authorized_test_accounts == ()
    assert d.special_notes == ""


def test_read_roe_missing_file_returns_default(tmp_path: Path) -> None:
    r = read_roe(tmp_path / "roe.md")
    assert r == default_roe()


def test_read_roe_parses_full_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text(
        "---\n"
        "dos_authorized: true\n"
        "destructive_payloads_authorized: true\n"
        "social_engineering_authorized: false\n"
        "pii_handling: synthetic_data_only\n"
        "max_requests_per_second: 100\n"
        "authorized_test_environments:\n"
        "  - staging.example.com\n"
        "  - sandbox.example.com\n"
        "authorized_test_accounts:\n"
        "  - bb+test1@cocode.dk\n"
        "special_notes: |\n"
        "  Program brief authorizes load test on /api/v2/*.\n"
        "---\n"
        "free body text\n",
        encoding="utf-8",
    )
    r = read_roe(tmp_path / "roe.md")
    assert r.dos_authorized is True
    assert r.destructive_payloads_authorized is True
    assert r.social_engineering_authorized is False
    assert r.pii_handling == "synthetic_data_only"
    assert r.max_requests_per_second == 100
    assert r.authorized_test_environments == (
        "staging.example.com",
        "sandbox.example.com",
    )
    assert r.authorized_test_accounts == ("bb+test1@cocode.dk",)
    assert "load test" in r.special_notes


def test_read_roe_partial_frontmatter_fills_defaults(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text(
        "---\nmax_requests_per_second: 50\n---\n", encoding="utf-8",
    )
    r = read_roe(tmp_path / "roe.md")
    assert r.max_requests_per_second == 50
    assert r.dos_authorized is False  # unspecified → floor
    assert r.pii_handling == "one_redacted_screenshot"


def test_read_roe_rejects_unknown_pii_handling(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text(
        "---\npii_handling: anything_goes\n---\n", encoding="utf-8",
    )
    with pytest.raises(InvalidRoE):
        read_roe(tmp_path / "roe.md")


def test_read_roe_rejects_non_positive_rate(tmp_path: Path) -> None:
    for value in (-5, 0):
        (tmp_path / "roe.md").write_text(
            f"---\nmax_requests_per_second: {value}\n---\n", encoding="utf-8",
        )
        with pytest.raises(InvalidRoE):
            read_roe(tmp_path / "roe.md")


def test_read_roe_rejects_non_bool_dos_authorized(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text(
        "---\ndos_authorized: maybe\n---\n", encoding="utf-8",
    )
    with pytest.raises(InvalidRoE):
        read_roe(tmp_path / "roe.md")


def test_read_roe_rejects_malformed_yaml(tmp_path: Path) -> None:
    (tmp_path / "roe.md").write_text("---\n: : :\n---\n", encoding="utf-8")
    with pytest.raises(InvalidRoE):
        read_roe(tmp_path / "roe.md")


def test_roe_is_frozen_dataclass() -> None:
    from dataclasses import FrozenInstanceError
    r = default_roe()
    with pytest.raises(FrozenInstanceError):
        r.max_requests_per_second = 999  # type: ignore[misc]
    assert isinstance(r, RoE)
