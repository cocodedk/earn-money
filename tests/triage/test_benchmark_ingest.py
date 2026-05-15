"""Tests for the disclosure-replay benchmark ingest CLI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from earn_money import config, db
from earn_money.triage import benchmark_ingest
from tests.triage.conftest import register_program

_SAMPLE_CORPUS = {
    "program": "hackerone/example",
    "source": "test fixture",
    "generated_at": "2026-05-15T09:30:00Z",
    "in_window_range": "2023-01-01 to present",
    "disclosed_date_precision_note": "approximate ±6 months",
    "disclosures": [
        {
            "report_url": "https://hackerone.com/reports/111",
            "title": "Test IDOR",
            "severity": "high",
            "disclosed_date": "2024-04",
            "bounty_usd": 500,
            "asset_pattern": "api.example.com/v1/users/{id}",
            "vuln_class": "IDOR",
            "vector_summary": "Auth'd user changes id param to read other users.",
            "auto_detectable_hint": "requires-auth",
        },
        {
            "report_url": "https://hackerone.com/reports/222",
            "title": "Test Info-Disclosure",
            "severity": "medium",
            "disclosed_date": "2024-08",
            "bounty_usd": None,
            "asset_pattern": "*.example.com /.git/",
            "vuln_class": "Info-Disclosure",
            "vector_summary": "Exposed .git directory leaks source code.",
            "auto_detectable_hint": "regex-friendly",
        },
    ],
    "summary": {"count": 2},
}


def _seed_corpus(tmp_repo: Path) -> Path:
    d = tmp_repo / "benchmarks" / "disclosures"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "hackerone-example.json"
    p.write_text(json.dumps(_SAMPLE_CORPUS), encoding="utf-8")
    return p


def test_ingest_writes_rows(tmp_repo: Path) -> None:
    register_program(config.Paths.from_root(tmp_repo))
    _seed_corpus(tmp_repo)

    rc = benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])

    assert rc == 0
    paths = config.Paths.from_root(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT report_url, vuln_class, severity, bounty_usd, "
        "auto_detectable_hint, verdict FROM benchmark_disclosures "
        "ORDER BY report_url"
    ).fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0] == (
        "https://hackerone.com/reports/111", "IDOR", "high", 500,
        "requires-auth", None,  # verdict starts NULL (unscored)
    )
    assert rows[1] == (
        "https://hackerone.com/reports/222", "Info-Disclosure", "medium", None,
        "regex-friendly", None,
    )


def test_ingest_sets_eligibility_from_corpus(tmp_repo: Path) -> None:
    """Rows with explicit in_window: false land as in_window_eligible=0;
    rows without the field default to 1 (matches the actual corpus shape
    where only algolia's historical anchors carry the field)."""
    register_program(config.Paths.from_root(tmp_repo))
    corpus = json.loads(json.dumps(_SAMPLE_CORPUS))
    corpus["disclosures"][0]["in_window"] = False
    # second row has no in_window field — implicit True
    d = tmp_repo / "benchmarks" / "disclosures"
    d.mkdir(parents=True, exist_ok=True)
    (d / "hackerone-example.json").write_text(json.dumps(corpus), encoding="utf-8")

    rc = benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])
    assert rc == 0

    paths = config.Paths.from_root(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT report_url, in_window_eligible FROM benchmark_disclosures "
        "ORDER BY report_url"
    ).fetchall()
    conn.close()

    assert rows == [
        ("https://hackerone.com/reports/111", 0),  # explicit in_window: false
        ("https://hackerone.com/reports/222", 1),  # implicit True
    ]


def test_ingest_self_heals_stale_scorer_verdict_on_eligibility_flip(
    tmp_repo: Path,
) -> None:
    """When a row flips to in_window_eligible=0, ingest clears scorer-owned
    verdict state (operator verdicts preserved separately)."""
    register_program(config.Paths.from_root(tmp_repo))
    _seed_corpus(tmp_repo)  # both rows eligible
    benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])

    paths = config.Paths.from_root(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    # Simulate a scorer verdict landing on row 111.
    conn.execute(
        "UPDATE benchmark_disclosures SET verdict = ?, verdict_reason = ?, "
        "verdict_set_at = ?, verdict_source = ?, scoring_rubric_version = ? "
        "WHERE report_url = ?",
        ("FN", "no plugin", "2026-05-15T10:00:00Z", "scorer", "1",
         "https://hackerone.com/reports/111"),
    )
    conn.commit()
    conn.close()

    # Flip the corpus to mark row 111 as out-of-window, re-ingest.
    p = tmp_repo / "benchmarks" / "disclosures" / "hackerone-example.json"
    corpus = json.loads(p.read_text())
    corpus["disclosures"][0]["in_window"] = False
    p.write_text(json.dumps(corpus), encoding="utf-8")

    benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])

    conn = db.open_db(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT in_window_eligible, verdict, verdict_reason, verdict_source, "
        "scoring_rubric_version FROM benchmark_disclosures WHERE report_url = ?",
        ("https://hackerone.com/reports/111",),
    ).fetchone()
    conn.close()

    assert row == (0, None, None, None, None)


def test_ingest_preserves_operator_verdict_on_eligibility_flip(
    tmp_repo: Path,
) -> None:
    """Operator verdicts survive an eligibility flip — only scorer verdicts
    are self-healed."""
    register_program(config.Paths.from_root(tmp_repo))
    _seed_corpus(tmp_repo)
    benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])

    paths = config.Paths.from_root(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    conn.execute(
        "UPDATE benchmark_disclosures SET verdict = ?, verdict_reason = ?, "
        "verdict_set_at = ?, verdict_source = ?, scoring_rubric_version = ? "
        "WHERE report_url = ?",
        ("TP", "manually replayed, plugin fires", "2026-05-15T10:00:00Z",
         "operator", "1",
         "https://hackerone.com/reports/111"),
    )
    conn.commit()
    conn.close()

    p = tmp_repo / "benchmarks" / "disclosures" / "hackerone-example.json"
    corpus = json.loads(p.read_text())
    corpus["disclosures"][0]["in_window"] = False
    p.write_text(json.dumps(corpus), encoding="utf-8")

    benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])

    conn = db.open_db(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT in_window_eligible, verdict, verdict_source FROM "
        "benchmark_disclosures WHERE report_url = ?",
        ("https://hackerone.com/reports/111",),
    ).fetchone()
    conn.close()

    assert row == (0, "TP", "operator")


def test_ingest_records_provenance(tmp_repo: Path) -> None:
    """Provenance columns (corpus_source, corpus_generated_at, in_window_range,
    date_precision_note) must land alongside the disclosure row."""
    register_program(config.Paths.from_root(tmp_repo))
    _seed_corpus(tmp_repo)

    rc = benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])
    assert rc == 0

    paths = config.Paths.from_root(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT corpus_source, corpus_generated_at, in_window_range, "
        "date_precision_note, scoring_rubric_version "
        "FROM benchmark_disclosures WHERE report_url = ?",
        ("https://hackerone.com/reports/111",),
    ).fetchone()
    conn.close()

    assert row == (
        "test fixture", "2026-05-15T09:30:00Z", "2023-01-01 to present",
        "approximate ±6 months",
        None,  # scoring_rubric_version is reserved for Phase B
    )


def test_ingest_is_idempotent_and_preserves_verdicts(tmp_repo: Path) -> None:
    """Re-running ingest refreshes corpus fields but never overwrites a verdict
    an operator/Phase B has already set."""
    register_program(config.Paths.from_root(tmp_repo))
    _seed_corpus(tmp_repo)

    benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])

    paths = config.Paths.from_root(tmp_repo)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    conn.execute(
        "UPDATE benchmark_disclosures SET verdict = ?, "
        "verdict_reason = ?, verdict_set_at = ? WHERE report_url = ?",
        ("FN", "no plugin covers IDOR", "2026-05-15T10:00:00Z",
         "https://hackerone.com/reports/111"),
    )
    conn.commit()
    conn.close()

    # Mutate the corpus title to confirm refresh fields propagate.
    p = tmp_repo / "benchmarks" / "disclosures" / "hackerone-example.json"
    corpus = json.loads(p.read_text())
    corpus["disclosures"][0]["title"] = "Test IDOR (updated)"
    p.write_text(json.dumps(corpus), encoding="utf-8")

    rc = benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])
    assert rc == 0

    conn = db.open_db(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT title, verdict, verdict_reason FROM benchmark_disclosures "
        "WHERE report_url = ?",
        ("https://hackerone.com/reports/111",),
    ).fetchone()
    conn.close()

    assert row == ("Test IDOR (updated)", "FN", "no plugin covers IDOR")


def test_ingest_missing_corpus_exits_nonzero(tmp_repo: Path) -> None:
    register_program(config.Paths.from_root(tmp_repo))
    rc = benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])
    assert rc != 0


def test_ingest_unregistered_program_exits_nonzero(tmp_repo: Path) -> None:
    _seed_corpus(tmp_repo)
    rc = benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])
    assert rc != 0


def test_ingest_returns_summary_count(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    register_program(config.Paths.from_root(tmp_repo))
    _seed_corpus(tmp_repo)

    benchmark_ingest.main([
        "--platform", "hackerone", "--program", "example", "--root", str(tmp_repo)
    ])

    captured = capsys.readouterr()
    assert "2" in captured.out  # 2 disclosures ingested
