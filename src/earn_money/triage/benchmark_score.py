"""Disclosure-replay benchmark scoring.

Loads `benchmarks/coverage_map.yaml`, walks `benchmark_disclosures` rows,
applies the truth table (see docs/superpowers/specs/2026-05-15-benchmark-
disclosures.md), writes verdicts back. Emits a per-program markdown
report at `benchmarks/scores/<platform>-<slug>.md`.

The atomic conditional UPDATE preserves operator verdicts and respects
rubric versioning (CAST(version AS INTEGER) avoids lexicographic
comparison pitfalls).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from earn_money import config, db
from earn_money._time import now_iso
from earn_money.triage.coverage_map import (
    CoverageMap,
    CoverageMapNotFound,
    CoverageMapVersionMismatch,
    _verdict_for,
    load_coverage_map,
)


@dataclass(frozen=True)
class ScoringSummary:
    program: str
    rubric_version: int
    rows_total: int
    rows_scored: int
    by_verdict: dict[str, int]
    excluded: int


def score_program(
    paths: config.Paths,
    *,
    platform: str,
    slug: str,
    cmap: CoverageMap | None = None,
) -> ScoringSummary:
    """Score every eligible row in the program's benchmark_disclosures table."""
    if cmap is None:
        cmap = load_coverage_map(paths)

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        rows = conn.execute(
            "SELECT report_url, vuln_class, auto_detectable_hint, "
            "in_window_eligible, verdict, verdict_source "
            "FROM benchmark_disclosures"
        ).fetchall()

        version_str = str(cmap.version)
        scored = 0
        now = now_iso()
        for report_url, vuln_class, hint, eligible, _v, _vs in rows:
            if not eligible:
                continue
            verdict, reason = _verdict_for(vuln_class, hint, cmap)
            cursor = conn.execute(
                """
                UPDATE benchmark_disclosures
                SET    verdict = ?, verdict_reason = ?, verdict_set_at = ?,
                       verdict_source = 'scorer', scoring_rubric_version = ?
                WHERE  report_url = ?
                  AND  in_window_eligible = 1
                  AND  (verdict IS NULL
                        OR (verdict_source = 'scorer'
                            AND CAST(scoring_rubric_version AS INTEGER) < ?))
                """,
                (verdict, reason, now, version_str, report_url, cmap.version),
            )
            if cursor.rowcount > 0:
                scored += 1
        conn.commit()

        by_verdict, excluded = _collect_counts(conn)
    finally:
        conn.close()

    return ScoringSummary(
        program=f"{platform}/{slug}",
        rubric_version=cmap.version,
        rows_total=len(rows),
        rows_scored=scored,
        by_verdict=by_verdict,
        excluded=excluded,
    )


def _collect_counts(conn: sqlite3.Connection) -> tuple[dict[str, int], int]:
    by_verdict: dict[str, int] = {"TP": 0, "FN": 0, "inconclusive": 0}
    for verdict, n in conn.execute(
        "SELECT verdict, COUNT(*) FROM benchmark_disclosures "
        "WHERE verdict IS NOT NULL GROUP BY verdict"
    ):
        by_verdict[verdict] = n
    excluded = conn.execute(
        "SELECT COUNT(*) FROM benchmark_disclosures "
        "WHERE verdict IS NULL AND in_window_eligible = 0"
    ).fetchone()[0]
    return by_verdict, excluded


def main(argv: list[str] | None = None) -> int:
    from earn_money.triage.benchmark_report import render_report

    parser = argparse.ArgumentParser(prog="benchmark-score")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--assert-coverage-map-version", type=int, default=None,
        help="Fail if the YAML's coverage_map_version doesn't match.",
    )
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    try:
        cmap = load_coverage_map(paths)
        if (
            args.assert_coverage_map_version is not None
            and args.assert_coverage_map_version != cmap.version
        ):
            raise CoverageMapVersionMismatch(
                f"expected coverage_map_version={args.assert_coverage_map_version}, "
                f"got {cmap.version}"
            )
        summary = score_program(
            paths, platform=args.platform, slug=args.program, cmap=cmap,
        )
        report_path = render_report(
            paths, platform=args.platform, slug=args.program, summary=summary,
        )
    except (CoverageMapNotFound, CoverageMapVersionMismatch, ValueError) as e:
        print(f"benchmark-score: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(
        f"benchmark-score: {summary.program} v{summary.rubric_version} — "
        f"TP={summary.by_verdict.get('TP', 0)} "
        f"FN={summary.by_verdict.get('FN', 0)} "
        f"inconclusive={summary.by_verdict.get('inconclusive', 0)} "
        f"excluded={summary.excluded}  →  {report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
