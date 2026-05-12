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


def substitute_template(template_body: str, finding: findings.Finding) -> str:
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
    force: bool = False,
) -> Path:
    """Generate (or refuse to overwrite) reports/drafts/<hash>.md.

    Returns the path to the draft. Raises:
    - TemplateNotFound if the template is missing.
    - DraftAlreadyExists if the draft file already exists.
    - ValueError if the finding hash is not in the DB.
    - ValueError if the program is not registered (no scope.md).
    """
    if "/" in finding_hash or ".." in finding_hash or finding_hash == "":
        raise ValueError(f"invalid finding_hash: {finding_hash!r}")

    scope_file = paths.scope_file(platform, slug)
    if not scope_file.exists():
        raise ValueError(
            f"program {platform}/{slug!r} is not registered "
            f"(no scope.md at {scope_file})"
        )

    template_path = paths.root / "templates" / "report-draft.md"
    if not template_path.exists():
        raise TemplateNotFound(str(template_path))

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        finding = findings.find_by_hash(conn, finding_hash)
        if finding is None:
            raise ValueError(
                f"finding {finding_hash!r} not in {platform}/{slug} DB"
            )
        if not force and finding.current_state != "verified":
            raise ValueError(
                f"finding {finding_hash!r} is in state "
                f"{finding.current_state!r}, not 'verified'. "
                f"Pass --force to draft anyway."
            )
    finally:
        conn.close()

    drafts_dir = paths.root / "reports" / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = drafts_dir / f"{finding_hash}.md"
    body = substitute_template(template_path.read_text(encoding="utf-8"), finding)
    try:
        with draft_path.open("x", encoding="utf-8") as fh:
            fh.write(body)
    except FileExistsError as exc:
        raise DraftAlreadyExists(str(draft_path)) from exc
    return draft_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="draft")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--hash", required=True, dest="finding_hash")
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Draft even if finding is not yet in 'verified' state.",
    )
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    try:
        path = draft_for(
            paths,
            platform=args.platform,
            slug=args.program,
            finding_hash=args.finding_hash,
            force=args.force,
        )
    except (TemplateNotFound, DraftAlreadyExists, ValueError) as e:
        print(f"draft: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"draft: wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
