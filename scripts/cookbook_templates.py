"""Template strings + section schemas for the cookbook bootstrap.

Kept separate from cookbook_bootstrap.py so the orchestrator stays under
the 200-line cap. Edit a template here, re-run the bootstrap to propagate.
"""
from __future__ import annotations

NEW_SPEC_SECTIONS = [
    "Purpose",
    "Inputs",
    "Detection logic",
    "Persistence",
    "Safety",
    "Pass/fail check",
    "Test fixtures",
    "Acceptance criteria",
]

# Mapping for migrating old-format specs (Intent/Detection technique/…) to new.
OLD_TO_NEW_SPEC = {
    "Intent": "Purpose",
    "Detection technique": "Detection logic",
    "Fixture": "Test fixtures",
    "Pass/fail check": "Pass/fail check",
    "Persistence": "Persistence",
    "AI involvement": "Safety",
}

NEW_SPEC_HINTS = {
    "Purpose": "<!-- One short paragraph: what this technique detects and why a runner cares. -->",
    "Inputs": "<!-- What the runner receives: target URL, optional credentials, config knobs. -->",
    "Detection logic": "<!-- Deterministic methods only: HTTP methods, headers, body patterns, paths, scanner capabilities. -->",
    "Persistence": "<!-- Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Define only stub-specific `<Name>Signature` and `<Name>Finding` types here. -->",
    "Safety": "<!-- Read-only vs mutating behavior. HTTP-method discipline. Payload restrictions. PII handling. AI involvement (default: None). -->",
    "Pass/fail check": "<!-- Explicit assertions, including negative ones (what must NOT happen). -->",
    "Test fixtures": "<!-- Which fixture(s) — `juice-shop` / `dvwa` / `webgoat` / new slug — and which feature in the container exposes the bug. -->",
    "Acceptance criteria": "<!-- Operational quality bar: idempotent, completes within budget, handles TLS errors gracefully, no flaky retries. -->",
}

PLAN_SECTIONS = ["Summary", "Files to touch", "TDD steps", "Verification", "Persistence wiring"]
PLAN_HINTS = {
    "Summary": "<!-- One short paragraph: what this plan ships. -->",
    "Files to touch": "<!-- Exact paths to create / modify (runner, test, schema, CLI). -->",
    "TDD steps": "<!-- Numbered: failing test → minimal impl → green → refactor → commit. -->",
    "Verification": "<!-- How we prove the implementation works against the fixture, end-to-end. -->",
    "Persistence wiring": "<!-- How findings from this runner flow into shared `ScanTarget` and `Evidence`, and into stub-specific Signature/Finding tables. -->",
}

SPEC_FRONTMATTER = """---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: {phase}
spec: {spec}
slug: {slug}
status: {status}     # pending | in-progress | blocked | done
fixture: {fixture}        # juice-shop | dvwa | webgoat | <name> | tbd
---
"""

PLAN_FRONTMATTER = """---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# seven lines intact. Values below the comments are yours to change.
phase: {phase}
spec: {spec}
slug: {slug}
spec_file: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/{phase_slug}/{spec_filename}
status: {status}           # pending | drafted | approved | implemented | verified
implementation_file: {impl}
test_file: {test}
---
"""

SPEC_MARKER = """<!--
GPT-5.5: Enrichment zone — paste-ready spec contract for LLM-assisted implementation.

Goal: enrich this spec so a coding agent can implement it safely and consistently.

PROTECTED — do not modify:
- YAML frontmatter (between `---` fences at top of file).
- Title heading, blockquote breadcrumb, and the `##` section headings.

EDITABLE — fill these:
- The body under each `##` section. Sub-headings (`###`), lists, code blocks, tables welcome.

OUTPUT FORMAT:
- Return raw markdown directly. Do NOT wrap the response in a ` ```markdown ` code fence.
- Inside the body, use exactly 3 backticks for code fences. No 4-backtick blocks.

CONTENT RULES:
- Use shared `ScanTarget` and `Evidence` from ../00-shared-schema.md. Do not redefine them.
- Define only stub-specific `<Name>Signature` and `<Name>Finding` types.
- Detection is deterministic. AI is `None` unless a deterministic gap is named under Safety.
- Pass/fail check has explicit assertions, including negative ones (what must NOT happen).
- Confidence: `low | medium | high`. Finding status: `candidate | confirmed | rejected | stale`.
- Never hard-code hostname → expected tech; detect from response evidence.
- Follow the Coding-agent rules in ../00-shared-schema.md.
-->

"""

PLAN_MARKER = """<!--
Planner / GPT-5.5: Enrichment zone — paste-ready plan contract for LLM-assisted implementation.

Goal: draft a plan a coding agent can execute step-by-step against the linked spec.

PROTECTED — do not modify:
- YAML frontmatter (between `---` fences at top of file).
- Title heading, Spec-reference blockquote, `##` section headings.

EDITABLE — fill these:
- The body under each `##` section.

OUTPUT FORMAT:
- Return raw markdown directly. No ` ```markdown ` wrapper. 3-backtick fences only.

CONTENT RULES:
- TDD steps must be numbered. Each step = (test name → minimal impl → commit message).
- File paths under `## Files to touch` are exact, distinguished as "create" vs "modify".
- `## Persistence wiring` references shared `ScanTarget` / `Evidence` from
  ../../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md — do not redefine.
-->

"""

PLANS_README = """# Cookbook Plans

Mirror tree of the [vuln-scanning cookbook specs](../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/).
Every spec at `<phase>/<spec>.md` has a matching plan file at the same path
here. The plan turns the spec into TDD steps + files-to-touch and tracks
implementation state via YAML frontmatter.

See the [cookbook README](../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/README.md)
for the full workflow.
"""

# Sentinels for idempotency detection.
NEW_SPEC_SENTINEL = "## Purpose"     # presence => already migrated to new structure
NEW_SPEC_MARKER_SENTINEL = "paste-ready spec contract for LLM-assisted implementation"
NEW_PLAN_MARKER_SENTINEL = "paste-ready plan contract for LLM-assisted implementation"
# Backward-compat alias used by older code paths.
NEW_MARKER_SENTINEL = NEW_SPEC_MARKER_SENTINEL
