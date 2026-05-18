"""One-shot bootstrap (idempotent) for the vuln-scanning cookbook.

For each section file under docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/:
  1. Convert bare spec stubs to YAML-frontmatter format (skip if already migrated).
  2. Create matching plan stubs at the mirror path under
     docs/superpowers/plans/2026-05-18-VULN-SCANNING-COOKBOOK/ (skip if exists).
  3. Ensure every spec and plan has the GPT-5.5 enrichment-zone marker block
     between the blockquote and the first `##` section (skip if already present).

Re-runnable any time. Safe to add new phases or sections and re-run.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPECS_ROOT = REPO / "docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK"
PLANS_ROOT = REPO / "docs/superpowers/plans/2026-05-18-VULN-SCANNING-COOKBOOK"

PHASE_DIR_RE = re.compile(r"^(\d{2})-(.+)$")
SPEC_FILE_RE = re.compile(r"^(\d{2})-(.+)\.md$")
OLD_TITLE_RE = re.compile(r"^# (\d+)\.(\d+)\s+(.+)$", re.MULTILINE)
OLD_BLOCKQUOTE_RE = re.compile(r"^> (Phase \d+ — .+)$", re.MULTILINE)

SENTINEL = "Enrichment zone — read before editing"

SPEC_MARKER = """<!--
GPT-5.5: Enrichment zone — read before editing.

PROTECTED — DO NOT MODIFY:
  - YAML frontmatter (between `---` fences at top of file). Managed by the rollup script.
  - The title heading (`# N.N <Bullet>`) and the blockquote breadcrumb above.
  - The `##` section headings below. Keep them verbatim; the rollup script and the
    matching plan both depend on the exact section names.

EDITABLE — FILL THESE:
  - The body under each `##` section heading. Replace the placeholder hint comments
    (`<!-- ... -->`) with concrete content.
  - Sub-headings (`###`), lists, code blocks, and tables welcome.
-->

"""

PLAN_MARKER = """<!--
Planner / GPT-5.5: Enrichment zone — read before editing.

PROTECTED — DO NOT MODIFY:
  - YAML frontmatter (between `---` fences at top of file). Managed by the rollup script.
  - The title heading (`# Plan: N.N <Bullet>`) and the Spec-reference blockquote above.
  - The `##` section headings below. Keep them verbatim.

EDITABLE — FILL THESE:
  - The body under each `##` section heading.
  - TDD steps must be numbered; everything else freeform.
-->

"""

SPEC_TEMPLATE = """---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: {phase}
spec: {spec}
slug: {slug}
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# {phase}.{spec} {title}

> {blockquote}

""" + SPEC_MARKER + """## Intent
<!-- One short paragraph: what this technique detects and why a runner cares. -->

## Detection technique
<!-- Deterministic tool, query, payload, or signature. Name the exact CLI, header, or pattern. -->

## Fixture
<!-- Which container exposes this bug, and how to reach it (URL, route, parameter). -->

## Pass/fail check
<!-- Exact assertion that proves the detection works against the fixture. -->

## Persistence
<!-- Shape of the finding when written to the backend (JSON keys / DB columns). -->

## AI involvement
<!-- Usually 'none'. If AI is needed, name the deterministic gap that justifies it. -->
"""

PLAN_TEMPLATE = """---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# seven lines intact. Values below the comments are yours to change.
phase: {phase}
spec: {spec}
slug: {slug}
spec_file: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/{phase_slug}/{spec_filename}
status: pending           # pending | drafted | approved | implemented | verified
implementation_file: null
test_file: null
---

# Plan: {phase}.{spec} {title}

> Spec: [`{phase_slug}/{spec_filename}`](../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/{phase_slug}/{spec_filename})

""" + PLAN_MARKER + """## Summary
<!-- One short paragraph: what this plan ships. -->

## Files to touch
<!-- Exact paths to create / modify (runner, test, schema, CLI). -->

## TDD steps
<!-- Numbered: failing test → minimal impl → green → refactor → commit. -->

## Verification
<!-- How we prove the implementation works against the fixture, end-to-end. -->

## Persistence wiring
<!-- How findings from this runner are written into the backend. -->
"""

PLANS_README = """# Cookbook Plans

Mirror tree of the [vuln-scanning cookbook specs](../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/).
Every spec at `<phase>/<spec>.md` has a matching plan file at the same path
here. The plan turns the spec into TDD steps + files-to-touch and tracks
implementation state via YAML frontmatter.

See the [cookbook README](../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/README.md)
for the full workflow.
"""


def already_migrated(path: Path) -> bool:
    return path.read_text(encoding="utf-8").startswith("---\n")


def ensure_marker(path: Path, marker: str, anchor: str) -> bool:
    """Insert marker before anchor if not already present. Returns True if changed."""
    text = path.read_text(encoding="utf-8")
    if SENTINEL in text:
        return False
    if anchor not in text:
        return False
    path.write_text(text.replace(anchor, marker + anchor, 1), encoding="utf-8")
    return True


def extract_old_meta(text: str) -> tuple[int, int, str, str]:
    title_m = OLD_TITLE_RE.search(text)
    bq_m = OLD_BLOCKQUOTE_RE.search(text)
    phase = int(title_m.group(1)) if title_m else 0
    spec = int(title_m.group(2)) if title_m else 0
    title = title_m.group(3).strip() if title_m else ""
    blockquote = bq_m.group(1).strip() if bq_m else f"Phase {phase}"
    return phase, spec, title, blockquote


def main() -> int:
    if not SPECS_ROOT.exists():
        print(f"error: specs folder not found: {SPECS_ROOT}", file=sys.stderr)
        return 1

    PLANS_ROOT.mkdir(parents=True, exist_ok=True)
    readme = PLANS_ROOT / "README.md"
    if not readme.exists():
        readme.write_text(PLANS_README)

    spec_migrated = spec_marked = 0
    plan_created = plan_marked = 0

    for phase_dir in sorted(SPECS_ROOT.iterdir()):
        if not phase_dir.is_dir():
            continue
        m = PHASE_DIR_RE.match(phase_dir.name)
        if not m:
            continue
        phase_slug = phase_dir.name
        plan_phase = PLANS_ROOT / phase_slug
        plan_phase.mkdir(parents=True, exist_ok=True)

        for spec_path in sorted(phase_dir.glob("[0-9][0-9]-*.md")):
            if spec_path.name == "00-overview.md":
                continue
            spec_match = SPEC_FILE_RE.match(spec_path.name)
            if not spec_match:
                continue
            slug = spec_match.group(2)

            if not already_migrated(spec_path):
                old = spec_path.read_text(encoding="utf-8")
                phase, spec_num, title, blockquote = extract_old_meta(old)
                spec_path.write_text(SPEC_TEMPLATE.format(
                    phase=phase, spec=spec_num, slug=slug,
                    title=title, blockquote=blockquote,
                ))
                spec_migrated += 1
            else:
                phase = int(phase_slug[:2])
                spec_num = int(spec_match.group(1))
                title = slug.replace("-", " ").capitalize()

            if ensure_marker(spec_path, SPEC_MARKER, "## Intent\n"):
                spec_marked += 1

            plan_path = plan_phase / spec_path.name
            if not plan_path.exists():
                plan_path.write_text(PLAN_TEMPLATE.format(
                    phase=phase, spec=spec_num, slug=slug, title=title,
                    phase_slug=phase_slug, spec_filename=spec_path.name,
                ))
                plan_created += 1
            if ensure_marker(plan_path, PLAN_MARKER, "## Summary\n"):
                plan_marked += 1

    print(
        f"specs: migrated {spec_migrated}, marker added to {spec_marked}\n"
        f"plans: created {plan_created}, marker added to {plan_marked}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
