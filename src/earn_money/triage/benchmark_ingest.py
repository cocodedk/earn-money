"""Disclosure-replay benchmark ingest.

Reads `benchmarks/disclosures/<platform>-<slug>.json` and upserts its
`disclosures[]` array into the program's `benchmark_disclosures` table.
Idempotent: re-running refreshes corpus fields but preserves any verdict
columns already set by Phase B scoring or by the operator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from earn_money import config, db
from earn_money._time import now_iso


class CorpusNotFound(FileNotFoundError):
    """Raised when the JSON corpus file does not exist."""


class ProgramNotRegistered(Exception):
    """Raised when the program has no scope.md (so ingest is premature)."""


def _corpus_path(paths: config.Paths, platform: str, slug: str) -> Path:
    return paths.root / "benchmarks" / "disclosures" / f"{platform}-{slug}.json"


def ingest(
    paths: config.Paths,
    *,
    platform: str,
    slug: str,
) -> int:
    """Ingest the disclosure corpus for one program. Returns row count."""
    if not paths.scope_file(platform, slug).exists():
        raise ProgramNotRegistered(
            f"program {platform}/{slug!r} has no scope.md — register before ingest"
        )

    corpus_file = _corpus_path(paths, platform, slug)
    if not corpus_file.exists():
        raise CorpusNotFound(str(corpus_file))

    data: dict[str, Any] = json.loads(corpus_file.read_text(encoding="utf-8"))
    rows = data.get("disclosures") or []
    ingested_at = now_iso()
    # Provenance — replicated per row so each disclosure carries its origin.
    corpus_source = str(data.get("source") or "")
    corpus_generated_at = str(data.get("generated_at") or "")
    in_window_range = str(data.get("in_window_range") or "")
    date_precision_note = data.get("disclosed_date_precision_note")

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        # Upsert: refresh corpus + provenance fields, preserve verdict columns.
        for row in rows:
            conn.execute(
                """
                INSERT INTO benchmark_disclosures (
                    report_url, title, severity, disclosed_date, bounty_usd,
                    asset_pattern, vuln_class, vector_summary,
                    auto_detectable_hint, ingested_at,
                    corpus_source, corpus_generated_at, in_window_range,
                    date_precision_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_url) DO UPDATE SET
                    title = excluded.title,
                    severity = excluded.severity,
                    disclosed_date = excluded.disclosed_date,
                    bounty_usd = excluded.bounty_usd,
                    asset_pattern = excluded.asset_pattern,
                    vuln_class = excluded.vuln_class,
                    vector_summary = excluded.vector_summary,
                    auto_detectable_hint = excluded.auto_detectable_hint,
                    ingested_at = excluded.ingested_at,
                    corpus_source = excluded.corpus_source,
                    corpus_generated_at = excluded.corpus_generated_at,
                    in_window_range = excluded.in_window_range,
                    date_precision_note = excluded.date_precision_note
                """,
                (
                    row["report_url"],
                    row["title"],
                    row["severity"],
                    row["disclosed_date"],
                    row.get("bounty_usd"),
                    row["asset_pattern"],
                    row["vuln_class"],
                    row["vector_summary"],
                    row["auto_detectable_hint"],
                    ingested_at,
                    corpus_source,
                    corpus_generated_at,
                    in_window_range,
                    date_precision_note,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark-ingest")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    try:
        n = ingest(paths, platform=args.platform, slug=args.program)
    except (CorpusNotFound, ProgramNotRegistered) as e:
        print(f"benchmark-ingest: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"benchmark-ingest: {n} disclosures ingested for {args.platform}/{args.program}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
