"""Generate a starting-draft report from a finding row + template.

The template at templates/report-draft.md is the starting point; the
operator's substantive edit pass is what turns it into a real report.
This module's job is just placeholder substitution, not authoring.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from earn_money import config, db
from earn_money.triage import findings


class DraftAlreadyExists(Exception):
    """Raised when reports/drafts/<hash>.md already exists. We never
    overwrite — the operator may have edited it."""


class TemplateNotFound(Exception):
    """Raised when templates/report-draft.md is missing from the repo."""


def render(template_body: str, finding: findings.Finding) -> str:
    """Substitute {{placeholder}} tokens with finding field values."""
    fields: dict[str, str] = {
        "finding_hash": finding.finding_hash,
        "platform": finding.platform,
        "slug": finding.slug,
        "vuln_class": finding.vuln_class,
        "asset": finding.asset,
        "target": finding.target,
        "signature": finding.signature,
        "title": finding.title,
        "severity_hint": finding.severity_hint,
        "source_tool": finding.source_tool,
        "source_run_id": finding.source_run_id,
        "evidence_path": finding.evidence_path,
        "first_seen": finding.first_seen,
    }

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(fields.get(key, f"{{{{{key}}}}}"))

    return re.sub(r"\{\{(\w+)\}\}", replace, template_body)


def draft_for(
    paths: config.Paths,
    *,
    platform: str,
    slug: str,
    finding_hash: str,
) -> Path:
    """Generate (or refuse to overwrite) reports/drafts/<hash>.md.

    Returns the path to the draft. Raises:
    - TemplateNotFound if the template is missing.
    - DraftAlreadyExists if the draft file already exists.
    - ValueError if the finding hash is not in the DB.
    """
    template_path = paths.root / "templates" / "report-draft.md"
    if not template_path.exists():
        raise TemplateNotFound(str(template_path))

    drafts_dir = paths.root / "reports" / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = drafts_dir / f"{finding_hash}.md"
    if draft_path.exists():
        raise DraftAlreadyExists(str(draft_path))

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        finding = findings.find_by_hash(conn, finding_hash)
        if finding is None:
            raise ValueError(
                f"finding {finding_hash!r} not in {platform}/{slug} DB"
            )
    finally:
        conn.close()

    body = render(template_path.read_text(encoding="utf-8"), finding)
    draft_path.write_text(body, encoding="utf-8")
    return draft_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="draft")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--hash", required=True, dest="finding_hash")
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    try:
        path = draft_for(
            paths,
            platform=args.platform,
            slug=args.program,
            finding_hash=args.finding_hash,
        )
    except (TemplateNotFound, DraftAlreadyExists, ValueError) as e:
        print(f"draft: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"draft: wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
