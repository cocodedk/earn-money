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
from typing import Any

import yaml

from earn_money import config, db
from earn_money._time import now_iso

_REPORT_DIR = "benchmarks/scores"


class CoverageMapNotFound(FileNotFoundError):
    """Raised when `benchmarks/coverage_map.yaml` is missing."""


class CoverageMapVersionMismatch(Exception):
    """Raised when --assert-coverage-map-version disagrees with the YAML."""


@dataclass(frozen=True)
class CoverageEntry:
    vuln_class: str
    plugins: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class CoverageMap:
    version: int
    entries: dict[str, CoverageEntry]


def load_coverage_map(paths: config.Paths) -> CoverageMap:
    """Read benchmarks/coverage_map.yaml and validate the version field."""
    p = paths.root / "benchmarks" / "coverage_map.yaml"
    if not p.exists():
        raise CoverageMapNotFound(str(p))
    data: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    version_raw = data.get("coverage_map_version")
    if not isinstance(version_raw, int):
        raise ValueError(
            f"coverage_map.yaml: coverage_map_version must be integer, "
            f"got {type(version_raw).__name__}"
        )
    entries: dict[str, CoverageEntry] = {}
    for raw in data.get("coverage") or []:
        cls = str(raw["vuln_class"])
        entries[cls] = CoverageEntry(
            vuln_class=cls,
            plugins=tuple(raw.get("plugins") or ()),
            notes=str(raw.get("notes") or ""),
        )
    return CoverageMap(version=version_raw, entries=entries)


# Truth-table verdict per (has_plugins, hint).
_FN_HINTS = frozenset({"requires-auth", "requires-business-logic",
                       "requires-payload-crafting"})
_INCONCLUSIVE_HINTS = frozenset({"regex-friendly", "requires-chain",
                                 "requires-fuzzing", "unclear"})


def _verdict_for(vuln_class: str, hint: str, cmap: CoverageMap) -> tuple[str, str]:
    """Apply the truth table from the spec. Returns (verdict, reason)."""
    entry = cmap.entries.get(vuln_class)
    if entry is None or not entry.plugins:
        return ("FN", f"no plugin covers {vuln_class}")
    plugins_str = ", ".join(entry.plugins)
    if hint in _FN_HINTS:
        return ("FN", f"plugin(s) [{plugins_str}] cover {vuln_class} class but "
                      f"hint={hint} requires capability we lack")
    if hint in _INCONCLUSIVE_HINTS:
        return ("inconclusive", f"plugin(s) [{plugins_str}] cover {vuln_class}; "
                                f"hint={hint} — operator review needed")
    return ("inconclusive", f"plugin(s) [{plugins_str}] cover {vuln_class}; "
                            f"hint={hint!r} unrecognised — operator review needed")


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


def render_report(
    paths: config.Paths, *, platform: str, slug: str, summary: ScoringSummary
) -> Path:
    """Render the per-program markdown report to benchmarks/scores/."""
    conn = db.open_db(paths.program_db(platform, slug))
    try:
        rows = conn.execute(
            "SELECT verdict, vuln_class, severity, report_url, "
            "verdict_reason, in_window_eligible, verdict_source "
            "FROM benchmark_disclosures "
            "ORDER BY in_window_eligible DESC, "
            "CASE verdict WHEN 'FN' THEN 0 WHEN 'inconclusive' THEN 1 "
            "             WHEN 'TP' THEN 2 ELSE 3 END, "
            "report_url"
        ).fetchall()

        per_class = conn.execute(
            """
            SELECT vuln_class,
                   SUM(CASE WHEN verdict = 'TP' THEN 1 ELSE 0 END) AS tp,
                   SUM(CASE WHEN verdict = 'FN' THEN 1 ELSE 0 END) AS fn,
                   SUM(CASE WHEN verdict = 'inconclusive' THEN 1 ELSE 0 END) AS incon,
                   SUM(CASE WHEN verdict IS NULL AND in_window_eligible = 0
                            THEN 1 ELSE 0 END) AS excluded
            FROM benchmark_disclosures
            GROUP BY vuln_class
            ORDER BY vuln_class
            """
        ).fetchall()
    finally:
        conn.close()

    cmap = load_coverage_map(paths)
    plugins_for: dict[str, str] = {
        cls: ", ".join(e.plugins) if e.plugins else "(none)"
        for cls, e in cmap.entries.items()
    }

    lines: list[str] = []
    lines.append(f"# Disclosure-replay scores — {summary.program}")
    lines.append("")
    lines.append(f"- Generated: {now_iso()}")
    lines.append(f"- coverage_map_version applied: {summary.rubric_version}")
    lines.append(f"- Rows total: {summary.rows_total}  "
                 f"(scored this pass: {summary.rows_scored})")
    lines.append(f"- Verdict counts — "
                 f"TP {summary.by_verdict.get('TP', 0)}, "
                 f"FN {summary.by_verdict.get('FN', 0)}, "
                 f"inconclusive {summary.by_verdict.get('inconclusive', 0)}, "
                 f"excluded {summary.excluded}")
    lines.append("")
    lines.append("## Summary by vuln_class")
    lines.append("")
    lines.append("| vuln_class | TP | FN | inconclusive | excluded | plugins |")
    lines.append("|---|---|---|---|---|---|")
    for cls, tp, fn, incon, excluded in per_class:
        lines.append(f"| {cls} | {tp} | {fn} | {incon} | {excluded} | "
                     f"{plugins_for.get(cls, '(class not in map)')} |")
    lines.append("")
    lines.append("## Detail (FN first)")
    lines.append("")
    lines.append("| verdict | vuln_class | severity | report_url | reason | "
                 "eligible | source |")
    lines.append("|---|---|---|---|---|---|---|")
    for verdict, vc, sev, url, reason, elig, src in rows:
        verdict_cell = verdict if verdict else (
            "excluded" if not elig else "unscored"
        )
        reason_cell = reason or ""
        lines.append(f"| {verdict_cell} | {vc} | {sev} | {url} | "
                     f"{reason_cell} | {elig} | {src or ''} |")

    out = paths.root / _REPORT_DIR / f"{platform}-{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
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
