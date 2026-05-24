### Task 1 Step 3: Implementation code for target_intel.py

- [ ] **Step 3: Implement target_intel.py**

Create `backend/apps/agent/target_intel.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

@dataclass
class FormSignature:
    action: str
    method: str
    input_names: list[str]

@dataclass
class PriorCandidate:
    category: str
    description: str

@dataclass
class TargetIntel:
    source_session_id: str
    source_completed_at: datetime
    is_stale: bool
    known_routes: set[str] = field(default_factory=set)
    form_signatures: list[FormSignature] = field(default_factory=list)
    prior_candidates: list[PriorCandidate] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)

def build_target_intel(
    target,
    *,
    exclude_session_id: object | None = None,
    stale_after_days: int = 7,
    max_routes: int = 20,
    max_forms: int = 10,
    max_candidates: int = 10,
    max_notes: int = 5,
) -> TargetIntel | None:
    from .models import AgentSession, SessionStatus

    prior = (
        AgentSession.objects.filter(
            target=target,
            status=SessionStatus.COMPLETED,
        )
        .exclude(pk=exclude_session_id)
        .order_by("-finished_at")
        .first()
    )
    if prior is None or prior.finished_at is None:
        return None

    is_stale = (timezone.now() - prior.finished_at) > timedelta(days=stale_after_days)

    routes = _extract_routes(prior, max_routes)
    forms = _extract_form_signatures(prior, max_forms)
    candidates = _extract_candidates(prior, max_candidates)
    hypotheses = _extract_hypotheses(prior, max_notes)

    return TargetIntel(
        source_session_id=str(prior.pk),
        source_completed_at=prior.finished_at,
        is_stale=is_stale,
        known_routes=routes,
        form_signatures=forms,
        prior_candidates=candidates,
        hypotheses=hypotheses,
    )

def _extract_routes(session, max_routes: int) -> set[str]:
    notes = session.notes.filter(note_type="route").order_by("pk").values_list("content", flat=True)
    routes: set[str] = set()
    for content in notes:
        path = _clean_text(content.get("path", ""), limit=120) if isinstance(content, dict) else ""
        if path:
            routes.add(path)
        if len(routes) >= max_routes:
            break
    return routes

def _extract_form_signatures(session, max_forms: int) -> list[FormSignature]:
    notes = session.notes.filter(note_type="form").order_by("pk").values_list("content", flat=True)
    forms: list[FormSignature] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for content in notes:
        if not isinstance(content, dict):
            continue
        input_names = content.get("input_names") or content.get("inputs") or []
        if not isinstance(input_names, list):
            input_names = []
        if input_names and isinstance(input_names[0], dict):
            input_names = [i.get("name", "") for i in input_names]
        signature = FormSignature(
            action=_clean_text(content.get("action", ""), limit=120),
            method=_clean_text(content.get("method", "GET"), limit=12).upper(),
            input_names=sorted(_clean_text(i, limit=80) for i in input_names if i),
        )
        key = (signature.action, signature.method, tuple(signature.input_names))
        if signature.action and key not in seen:
            forms.append(signature)
            seen.add(key)
        if len(forms) >= max_forms:
            break
    return forms

def _extract_candidates(session, max_candidates: int) -> list[PriorCandidate]:
    from .models import AgentAction, ValidationStatus

    actions = AgentAction.objects.filter(
        turn__session=session,
        action_type="submit_candidate",
        validation_status=ValidationStatus.VALID,
    ).order_by("pk").values("goal", "args_redacted")[:max_candidates]

    results: list[PriorCandidate] = []
    for action in actions:
        args = action.get("args_redacted") or {}
        results.append(PriorCandidate(
            category=_clean_text(args.get("category", "unknown"), limit=80) or "unknown",
            description=_clean_text(action.get("goal", ""), limit=200),
        ))
    return results

def _extract_hypotheses(session, max_notes: int) -> list[str]:
    notes = session.notes.filter(note_type__in=["hypothesis", "gap"]).order_by("pk").values_list("content", flat=True)[:max_notes]
    results = []
    for content in notes:
        if isinstance(content, dict):
            text = content.get("text", "") or content.get("description", "")
        else:
            text = str(content)
        text = _clean_text(text, limit=200)
        if text:
            results.append(text)
    return results

def _clean_text(value, *, limit: int) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return " ".join(text.split())[:limit]

def format_intel_prompt(intel: TargetIntel | None) -> str:
    if intel is None:
        return ""
    freshness = "stale — treat with lower confidence" if intel.is_stale else "fresh"
    date_str = intel.source_completed_at.astimezone(dt_timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "## Prior Target Intel",
        "",
        f"Source session: {intel.source_session_id}, completed at {date_str}",
        f"Freshness: {freshness}",
        "",
        "These are unverified hints from a previous session. You must re-observe",
        "to get current element IDs. Prior candidates are re-check targets,",
        "not current evidence.",
    ]

    if intel.known_routes:
        lines.append("")
        lines.append("Known routes:")
        for route in sorted(intel.known_routes):
            lines.append(f"  {route}")

    if intel.form_signatures:
        lines.append("")
        lines.append("Forms to re-check:")
        for form in intel.form_signatures:
            fields = ", ".join(form.input_names) or "(no named inputs)"
            lines.append(f"  - {form.method} {form.action} inputs: {fields}")

    if intel.prior_candidates:
        lines.append("")
        lines.append("Prior candidates to re-check:")
        for c in intel.prior_candidates:
            lines.append(f"  - category: {c.category}")
            lines.append(f"    description: {c.description}")
            lines.append("    instruction: re-verify in current session")

    if intel.hypotheses:
        lines.append("")
        lines.append("Gaps / hypotheses:")
        for h in intel.hypotheses:
            lines.append(f"  - {h}")

    return "\n".join(lines)
```
