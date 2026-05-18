"""One-shot bootstrap (idempotent) for the vuln-scanning cookbook.

For each section under docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/:
  1. Migrate bare / old-format spec stubs to the current YAML-frontmatter format
     with the 8-section structure (Purpose / Inputs / Detection logic / Persistence
     / Safety / Pass/fail check / Test fixtures / Acceptance criteria). Strips any
     ChatGPT chat-envelope wrapper (`Here is the filled stub:` + `` ````markdown ``)
     and normalises 4-backtick fences to 3.
  2. Create matching plan stubs at the mirror path under
     docs/superpowers/plans/2026-05-18-VULN-SCANNING-COOKBOOK/ (skip if exists).
  3. Ensure every spec and plan has the current enrichment-zone marker block.

Re-runnable any time. Safe to add new phases or sections and re-run.

Templates and section schemas live in cookbook_templates.py.

=== SAFETY GATE ===

This script REWRITES every cookbook spec and plan stub from templates. It
preserves frontmatter values (status, fixture, …) and `##` section bodies, but
a templating bug or stale code could destroy enrichment in flight.

Default mode is DRY-RUN — it prints which files would change and exits without
writing. Pass --apply to actually write.

Usage:
  .venv/bin/python scripts/cookbook_bootstrap.py            # preview only
  .venv/bin/python scripts/cookbook_bootstrap.py --apply    # write changes
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from cookbook_templates import (
    NEW_PLAN_MARKER_SENTINEL,
    NEW_SPEC_HINTS,
    NEW_SPEC_MARKER_SENTINEL,
    NEW_SPEC_SECTIONS,
    NEW_SPEC_SENTINEL,
    OLD_TO_NEW_SPEC,
    PLAN_FRONTMATTER,
    PLAN_HINTS,
    PLAN_MARKER,
    PLAN_SECTIONS,
    PLANS_README,
    SPEC_FRONTMATTER,
    SPEC_MARKER,
)

REPO = Path(__file__).resolve().parent.parent
SPECS_ROOT = REPO / "docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK"
PLANS_ROOT = REPO / "docs/superpowers/plans/2026-05-18-VULN-SCANNING-COOKBOOK"

PHASE_DIR_RE = re.compile(r"^(\d{2})-(.+)$")
SPEC_FILE_RE = re.compile(r"^(\d{2})-(.+)\.md$")
OLD_TITLE_RE = re.compile(r"^# (\d+)\.(\d+)\s+(.+)$", re.MULTILINE)
PLAN_TITLE_RE = re.compile(r"^# Plan: (\d+)\.(\d+)\s+(.+)$", re.MULTILINE)
OLD_BLOCKQUOTE_RE = re.compile(r"^> (Phase \d+ — .+)$", re.MULTILINE)
SECTION_HEAD_RE = re.compile(r"^## (.+)$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def parse_frontmatter_field(block: str, key: str, default: str) -> str:
    """Return the value of `key: value` from a frontmatter block, stripping inline `# ...` hint comments."""
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*(?:#.*)?$", block, re.MULTILINE)
    return m.group(1).strip() if m else default


def parse_spec_frontmatter(text: str) -> tuple[str, str]:
    """Return (status, fixture) from existing spec frontmatter, or defaults."""
    m = FRONTMATTER_RE.search(text)
    if not m:
        return "pending", "tbd"
    block = m.group(1)
    return parse_frontmatter_field(block, "status", "pending"), parse_frontmatter_field(block, "fixture", "tbd")


def parse_plan_frontmatter(text: str) -> tuple[str, str, str]:
    """Return (status, implementation_file, test_file) from existing plan frontmatter, or defaults."""
    m = FRONTMATTER_RE.search(text)
    if not m:
        return "pending", "null", "null"
    block = m.group(1)
    return (
        parse_frontmatter_field(block, "status", "pending"),
        parse_frontmatter_field(block, "implementation_file", "null"),
        parse_frontmatter_field(block, "test_file", "null"),
    )


def strip_chatgpt_wrapper(text: str) -> str:
    """Strip ChatGPT chat-envelope wrapper if the file isn't clean markdown."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip() == "---"), 0)
    end = len(lines)
    while end > start:
        last = lines[end - 1].strip()
        if not last or set(last) == {"`"}:
            end -= 1
            continue
        break
    return "\n".join(lines[start:end]) + "\n"


def normalize_fences(text: str) -> str:
    """Replace bare 4-backtick fences with 3 (cookbook never nests code blocks)."""
    return re.sub(r"^````+\s*$", "```", text, flags=re.MULTILINE)


def parse_sections(text: str) -> dict[str, str]:
    """Return {heading: body} for every `##` section in the text."""
    sections: dict[str, str] = {}
    matches = list(SECTION_HEAD_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        stop = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[m.group(1).strip()] = text[start:stop].strip("\n")
    return sections


def is_placeholder(body: str) -> bool:
    """True if body is just a single-line hint comment (untouched template)."""
    s = body.strip()
    return s.startswith("<!--") and s.endswith("-->") and "\n" not in s


def render_spec(
    phase: int, spec: int, slug: str, title: str, blockquote: str,
    status: str, fixture: str, bodies: dict[str, str],
) -> str:
    out = [SPEC_FRONTMATTER.format(
        phase=phase, spec=spec, slug=slug, status=status, fixture=fixture,
    )]
    out.append(f"\n# {phase}.{spec} {title}\n\n")
    out.append(f"> {blockquote}\n\n")
    out.append(SPEC_MARKER)
    for heading in NEW_SPEC_SECTIONS:
        out.append(f"## {heading}\n\n{bodies[heading]}\n\n")
    return "".join(out).rstrip("\n") + "\n"


def render_plan(
    phase: int, spec: int, slug: str, title: str, phase_slug: str,
    spec_filename: str, status: str, impl: str, test: str, bodies: dict[str, str],
) -> str:
    out = [PLAN_FRONTMATTER.format(
        phase=phase, spec=spec, slug=slug,
        phase_slug=phase_slug, spec_filename=spec_filename,
        status=status, impl=impl, test=test,
    )]
    out.append(f"\n# Plan: {phase}.{spec} {title}\n\n")
    rel = f"../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/{phase_slug}/{spec_filename}"
    out.append(f"> Spec: [`{phase_slug}/{spec_filename}`]({rel})\n\n")
    out.append(PLAN_MARKER)
    for heading in PLAN_SECTIONS:
        out.append(f"## {heading}\n\n{bodies[heading]}\n\n")
    return "".join(out).rstrip("\n") + "\n"


def extract_meta(text: str, plan: bool = False) -> tuple[int, int, str, str]:
    """Return (phase, spec, title, blockquote) parsed from an existing file."""
    title_re = PLAN_TITLE_RE if plan else OLD_TITLE_RE
    title_m = title_re.search(text)
    bq_m = OLD_BLOCKQUOTE_RE.search(text) if not plan else None
    phase = int(title_m.group(1)) if title_m else 0
    spec = int(title_m.group(2)) if title_m else 0
    title = title_m.group(3).strip() if title_m else ""
    blockquote = bq_m.group(1).strip() if bq_m else f"Phase {phase}"
    return phase, spec, title, blockquote


def needs_update(text: str) -> bool:
    """True if file is missing new section structure OR new spec marker."""
    return NEW_SPEC_SENTINEL not in text or NEW_SPEC_MARKER_SENTINEL not in text


def migrate_spec(spec_path: Path, fallback_meta: tuple[int, int, str, str]) -> bool:
    """Update a spec to the current shape. Returns True if changed."""
    text = spec_path.read_text(encoding="utf-8")
    if text.startswith("---\n") and not needs_update(text):
        return False
    status, fixture = parse_spec_frontmatter(text)
    text = normalize_fences(strip_chatgpt_wrapper(text))
    phase, spec, title, blockquote = extract_meta(text) if "---" in text else (0, 0, "", "")
    if not title:
        phase, spec, title, blockquote = fallback_meta
    old_sections = parse_sections(text)
    bodies: dict[str, str] = {}
    for new_h in NEW_SPEC_SECTIONS:
        old_h = next((o for o, n in OLD_TO_NEW_SPEC.items() if n == new_h), None)
        body = old_sections.get(old_h or new_h, "").strip() if old_h else old_sections.get(new_h, "").strip()
        bodies[new_h] = NEW_SPEC_HINTS[new_h] if not body or is_placeholder(body) else body
    spec_path.write_text(render_spec(
        phase, spec, _slug(spec_path), title, blockquote, status, fixture, bodies,
    ))
    return True


def migrate_plan(plan_path: Path, spec_path: Path, phase_slug: str) -> bool:
    """Ensure the plan stub exists and carries the current marker."""
    spec_meta = extract_meta(spec_path.read_text(encoding="utf-8"))
    phase, spec, title, _ = spec_meta
    if plan_path.exists():
        text = plan_path.read_text(encoding="utf-8")
        status, impl, test = parse_plan_frontmatter(text)
        if NEW_PLAN_MARKER_SENTINEL in text:
            return False
        bodies = {h: parse_sections(text).get(h, PLAN_HINTS[h]).strip() or PLAN_HINTS[h]
                  for h in PLAN_SECTIONS}
    else:
        status, impl, test = "pending", "null", "null"
        bodies = {h: PLAN_HINTS[h] for h in PLAN_SECTIONS}
    plan_path.write_text(render_plan(
        phase, spec, _slug(spec_path), title,
        phase_slug, spec_path.name, status, impl, test, bodies,
    ))
    return True


def _slug(spec_path: Path) -> str:
    m = SPEC_FILE_RE.match(spec_path.name)
    return m.group(2) if m else spec_path.stem


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap / migrate cookbook spec and plan stubs.",
        epilog="Default is DRY-RUN. Pass --apply to actually write changes.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write changes. Without this flag, the script previews changes only.",
    )
    args = parser.parse_args()

    if not SPECS_ROOT.exists():
        print(f"error: specs folder not found: {SPECS_ROOT}", file=sys.stderr)
        return 1

    if args.apply:
        print("APPLY MODE — writes are enabled.\n")
    else:
        print("DRY-RUN — no files will be written. Pass --apply to write.\n")

    if args.apply:
        PLANS_ROOT.mkdir(parents=True, exist_ok=True)
        readme = PLANS_ROOT / "README.md"
        if not readme.exists():
            readme.write_text(PLANS_README)

    spec_changes: list[Path] = []
    plan_changes: list[Path] = []

    for phase_dir in sorted(SPECS_ROOT.iterdir()):
        if not phase_dir.is_dir():
            continue
        m = PHASE_DIR_RE.match(phase_dir.name)
        if not m:
            continue
        phase_slug = phase_dir.name
        phase_n = int(m.group(1))
        plan_phase = PLANS_ROOT / phase_slug
        if args.apply:
            plan_phase.mkdir(parents=True, exist_ok=True)
        for spec_path in sorted(phase_dir.glob("[0-9][0-9]-*.md")):
            if spec_path.name == "00-overview.md":
                continue
            sm = SPEC_FILE_RE.match(spec_path.name)
            if not sm:
                continue
            fallback = (phase_n, int(sm.group(1)), sm.group(2).replace("-", " ").capitalize(),
                        f"Phase {phase_n}")
            if _spec_needs_migration(spec_path):
                spec_changes.append(spec_path)
                if args.apply:
                    migrate_spec(spec_path, fallback)
            plan_path = plan_phase / spec_path.name
            if _plan_needs_migration(plan_path):
                plan_changes.append(plan_path)
                if args.apply:
                    migrate_plan(plan_path, spec_path, phase_slug)

    verb = "updated" if args.apply else "would update"
    print(f"specs {verb}: {len(spec_changes)}")
    print(f"plans {verb}: {len(plan_changes)}")
    if spec_changes and not args.apply:
        print("\nfirst few specs that would change:")
        for p in spec_changes[:5]:
            print(f"  {p.relative_to(REPO)}")
    if plan_changes and not args.apply:
        print("\nfirst few plans that would change:")
        for p in plan_changes[:5]:
            print(f"  {p.relative_to(REPO)}")
    return 0


def _spec_needs_migration(spec_path: Path) -> bool:
    if not spec_path.exists():
        return True
    text = spec_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return True
    return needs_update(text)


def _plan_needs_migration(plan_path: Path) -> bool:
    if not plan_path.exists():
        return True
    text = plan_path.read_text(encoding="utf-8")
    return NEW_PLAN_MARKER_SENTINEL not in text


if __name__ == "__main__":
    raise SystemExit(main())
