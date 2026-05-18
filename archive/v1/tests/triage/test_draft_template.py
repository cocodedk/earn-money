"""Template-substitution tests for earn_money.triage.draft.

Split out from test_draft.py to keep both files under the 200-line cap.
These tests do not require a DB or a registered program — they exercise
substitute_template() directly and the committed templates/report-draft.md.
"""

from __future__ import annotations

import re
from pathlib import Path

from earn_money.triage import draft
from tests.triage.conftest import make_finding


def test_substitute_template_substitutes_fields() -> None:
    """Unit-test substitute_template() in isolation, without filesystem or DB."""
    template = "hash={{finding_hash}} title={{title}} unknown={{nope}}"
    f = make_finding(
        finding_hash="h1", title="MyTitle", current_state="verified",
        platform="p", slug="s", vuln_class="v", asset="a", target="t",
        signature="sig", severity_hint="high", confidence=80,
        source_tool="tool", source_run_id="rid", evidence_path="ep",
        notes_path="np", first_seen="ts", last_seen="ts",
    )
    result = draft.substitute_template(template, f)
    assert result == "hash=h1 title=MyTitle unknown={{nope}}"


def test_template_placeholders_are_all_substituted() -> None:
    """Every {{token}} in templates/report-draft.md is covered by the field dict."""
    repo_root = Path(__file__).parents[2]
    template_path = repo_root / "templates" / "report-draft.md"
    assert template_path.exists(), f"template missing: {template_path}"
    body = template_path.read_text(encoding="utf-8")
    tokens = set(re.findall(r"\{\{(\w+)\}\}", body))

    known_keys = {
        "finding_hash", "platform", "slug", "vuln_class", "asset", "target",
        "signature", "title", "severity_hint", "source_tool", "source_run_id",
        "evidence_path", "first_seen",
    }
    unknown = tokens - known_keys
    assert not unknown, (
        f"Template contains unknown placeholders (will not be substituted): {unknown}"
    )
