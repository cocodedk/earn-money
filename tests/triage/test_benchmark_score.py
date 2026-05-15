"""Tests for the disclosure-replay benchmark scoring engine."""
from __future__ import annotations

import json
from pathlib import Path

from earn_money import config, db
from earn_money.triage import benchmark_ingest, benchmark_score
from tests.triage.conftest import register_program

_COVERAGE_MAP_V1 = """\
coverage_map_version: 1
coverage:
  - vuln_class: Info-Disclosure
    plugins: [nuclei]
    notes: variant-dependent.
  - vuln_class: IDOR
    plugins: []
    notes: no plugin.
  - vuln_class: SSRF
    plugins: []
    notes: no plugin.
"""

_CORPUS: dict = {
    "program": "hackerone/example",
    "source": "test fixture",
    "generated_at": "2026-05-15T09:30:00Z",
    "in_window_range": "2023-01-01 to present",
    "disclosures": [
        {
            "report_url": "https://h1.com/1",
            "title": "IDOR no-plugin",
            "severity": "high",
            "disclosed_date": "2024-04",
            "asset_pattern": "*",
            "vuln_class": "IDOR",
            "vector_summary": "v",
            "auto_detectable_hint": "requires-auth",
        },
        {
            "report_url": "https://h1.com/2",
            "title": "Info-Disclosure regex-friendly",
            "severity": "low",
            "disclosed_date": "2024-04",
            "asset_pattern": "*",
            "vuln_class": "Info-Disclosure",
            "vector_summary": "v",
            "auto_detectable_hint": "regex-friendly",
        },
        {
            "report_url": "https://h1.com/3",
            "title": "Info-Disclosure requires-auth",
            "severity": "medium",
            "disclosed_date": "2024-04",
            "asset_pattern": "*",
            "vuln_class": "Info-Disclosure",
            "vector_summary": "v",
            "auto_detectable_hint": "requires-auth",
        },
        {
            "report_url": "https://h1.com/4",
            "title": "Out-of-window anchor",
            "severity": "low",
            "disclosed_date": "2020",
            "in_window": False,
            "asset_pattern": "*",
            "vuln_class": "Info-Disclosure",
            "vector_summary": "v",
            "auto_detectable_hint": "regex-friendly",
        },
    ],
    "summary": {},
}


def _setup(tmp_repo: Path) -> config.Paths:
    register_program(config.Paths.from_root(tmp_repo))
    d = tmp_repo / "benchmarks" / "disclosures"
    d.mkdir(parents=True, exist_ok=True)
    (d / "hackerone-example.json").write_text(json.dumps(_CORPUS), encoding="utf-8")
    (tmp_repo / "benchmarks" / "coverage_map.yaml").write_text(
        _COVERAGE_MAP_V1, encoding="utf-8"
    )
    benchmark_ingest.main(
        ["--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)]
    )
    return config.Paths.from_root(tmp_repo)


def test_score_assigns_verdicts_per_truth_table(tmp_repo: Path) -> None:
    paths = _setup(tmp_repo)
    rc = benchmark_score.main(
        ["--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)]
    )
    assert rc == 0

    conn = db.open_db(paths.program_db("hackerone", "example"))
    rows = {
        r[0]: (r[1], r[2], r[3], r[4])
        for r in conn.execute(
            "SELECT report_url, verdict, verdict_source, "
            "scoring_rubric_version, in_window_eligible "
            "FROM benchmark_disclosures ORDER BY report_url"
        )
    }
    conn.close()

    assert rows["https://h1.com/1"] == ("FN", "scorer", "1", 1)
    assert rows["https://h1.com/2"] == ("inconclusive", "scorer", "1", 1)
    assert rows["https://h1.com/3"] == ("FN", "scorer", "1", 1)
    # Out-of-window: scorer never writes.
    assert rows["https://h1.com/4"] == (None, None, None, 0)


def test_score_writes_markdown_report(tmp_repo: Path) -> None:
    _setup(tmp_repo)
    benchmark_score.main(
        ["--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)]
    )
    report = (tmp_repo / "benchmarks" / "scores" / "hackerone-example.md").read_text()
    assert "IDOR" in report
    assert "Info-Disclosure" in report
    assert "https://h1.com/1" in report
    assert "excluded" in report.lower()


def test_score_preserves_operator_verdict(tmp_repo: Path) -> None:
    paths = _setup(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    conn.execute(
        "UPDATE benchmark_disclosures SET verdict = ?, verdict_source = ?, "
        "scoring_rubric_version = ?, verdict_set_at = ? WHERE report_url = ?",
        ("TP", "operator", "1", "2026-05-15T10:00:00Z", "https://h1.com/1"),
    )
    conn.commit()
    conn.close()

    benchmark_score.main(
        ["--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)]
    )

    conn = db.open_db(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT verdict, verdict_source FROM benchmark_disclosures "
        "WHERE report_url = ?",
        ("https://h1.com/1",),
    ).fetchone()
    conn.close()
    assert row == ("TP", "operator")


def test_score_lexicographic_safety(tmp_repo: Path) -> None:
    """Version 2 must not overwrite a row at version 10 (lex '2' > '10';
    CAST in WHERE enforces numeric ordering)."""
    paths = _setup(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    conn.execute(
        "UPDATE benchmark_disclosures SET verdict = ?, verdict_source = ?, "
        "scoring_rubric_version = ?, verdict_set_at = ? WHERE report_url = ?",
        ("FN", "scorer", "10", "2026-05-15T10:00:00Z", "https://h1.com/1"),
    )
    conn.commit()
    conn.close()

    benchmark_score.main(
        ["--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)]
    )

    conn = db.open_db(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT verdict, scoring_rubric_version FROM benchmark_disclosures "
        "WHERE report_url = ?",
        ("https://h1.com/1",),
    ).fetchone()
    conn.close()
    assert row == ("FN", "10")


def test_score_assert_version_flag(tmp_repo: Path) -> None:
    """--assert-coverage-map-version=N exits non-zero on mismatch."""
    _setup(tmp_repo)
    rc = benchmark_score.main(
        ["--platform", "hackerone", "--program", "example",
         "--root", str(tmp_repo), "--assert-coverage-map-version", "999"]
    )
    assert rc != 0
