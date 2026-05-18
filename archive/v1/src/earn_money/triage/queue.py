"""Pure markdown rendering for `findings/_queue/<hash>.md`.

The render function is a starting draft — the operator's manual edit
pass is what turns this into a real triage note. Per CLAUDE.md, a
template that reads as "finished work" is a process smell.
"""

from __future__ import annotations

from earn_money.recon.services import HttpService
from earn_money.triage.findings import Finding

_CHECKLIST: tuple[str, ...] = (
    "Reproduce the matcher hit manually.",
    "Check whether the matched URL is reachable from an unauthenticated session.",
    "If the template is a CVE check, verify the running version actually corresponds "
    "to the vulnerable range — many CVE templates are version-sniff only and miss "
    "backported patches.",
    "Capture one redacted screenshot (no PII).",
    "Decide impact and write a one-paragraph rationale for whether this clears "
    "the program's severity bar.",
)


def render(f: Finding, *, service: HttpService | None) -> str:
    """Build the markdown body for findings/_queue/<finding_hash>.md."""
    return "".join((
        _frontmatter(f),
        _title(f),
        _scanner_block(f),
        _asset_block(service),
        _checklist_block(),
        _notes_block(),
    ))


def _frontmatter(f: Finding) -> str:
    lines = [
        "---",
        f"finding_hash: {f.finding_hash}",
        f"platform: {f.platform}",
        f"slug: {f.slug}",
        f"vuln_class: {f.vuln_class}",
        f"asset: {f.asset}",
        f"target: {f.target}",
        f"signature: {f.signature}",
        f"severity_hint: {f.severity_hint}",
        f"confidence: {f.confidence}",
        f"source_tool: {f.source_tool}",
        f"source_run_id: {f.source_run_id}",
        f"first_seen: {f.first_seen}",
        f"last_seen: {f.last_seen}",
        f"occurrence_count: {f.occurrence_count}",
        "state: queued",
        "---",
        "",
    ]
    return "\n".join(lines) + "\n"


def _title(f: Finding) -> str:
    return f"# {f.title}\n\n"


def _scanner_block(f: Finding) -> str:
    return (
        "## What the scanner said\n\n"
        f"{f.source_tool} matched **{f.signature}** on `{f.target}` "
        f"(severity hint: {f.severity_hint}, confidence: {f.confidence}%).\n\n"
        f"Evidence: `{f.evidence_path}`\n\n"
    )


def _asset_block(service: HttpService | None) -> str:
    if service is None:
        return (
            "## Asset context\n\n"
            "_no recent httpx observation for this asset — re-run httpx-probe "
            "before treating this as a real candidate._\n\n"
        )
    techs = ", ".join(service.technologies) if service.technologies else "(none reported)"
    return (
        "## Asset context\n\n"
        f"- Asset: `{service.subdomain}`\n"
        f"- Latest observation: {service.observed_at}  "
        f"(Status {service.status_code}, server `{service.server or 'unknown'}`)\n"
        f"- Technologies: {techs}\n\n"
    )


def _checklist_block() -> str:
    items = "\n".join(f"- [ ] {line}" for line in _CHECKLIST)
    return (
        "## What we need to confirm before this is a finding\n\n"
        f"{items}\n\n"
    )


def _notes_block() -> str:
    return (
        "## Operator notes\n"
        "<!-- write your verification trail here -->\n"
    )
