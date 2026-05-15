"""Per-program markdown report renderer for the disclosure-replay benchmark.

Extracted from benchmark_score.py — provides render_report().
"""

from __future__ import annotations

from pathlib import Path

from earn_money import config, db
from earn_money._time import now_iso
from earn_money.triage.benchmark_score import ScoringSummary
from earn_money.triage.coverage_map import load_coverage_map

_REPORT_DIR = "benchmarks/scores"


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
