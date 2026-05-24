"""Private extraction helpers for target_intel.py — not part of the public API."""
from __future__ import annotations

from .target_intel import FormSignature, PriorCandidate


def extract_routes(session, max_routes: int) -> set[str]:
    notes = (
        session.notes.filter(note_type="route")
        .order_by("pk")
        .values_list("content", flat=True)
    )
    routes: set[str] = set()
    for content in notes:
        path = (
            clean_text(content.get("path", ""), limit=120)
            if isinstance(content, dict)
            else ""
        )
        if path:
            routes.add(path)
        if len(routes) >= max_routes:
            break
    return routes


def extract_form_signatures(session, max_forms: int) -> list[FormSignature]:
    notes = (
        session.notes.filter(note_type="form")
        .order_by("pk")
        .values_list("content", flat=True)
    )
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
            action=clean_text(content.get("action", ""), limit=120),
            method=clean_text(content.get("method", "GET"), limit=12).upper(),
            input_names=sorted(clean_text(i, limit=80) for i in input_names if i),
        )
        key = (signature.action, signature.method, tuple(signature.input_names))
        if signature.action and key not in seen:
            forms.append(signature)
            seen.add(key)
        if len(forms) >= max_forms:
            break
    return forms


def extract_candidates(session, max_candidates: int) -> list[PriorCandidate]:
    from .models import AgentAction, ValidationStatus

    actions = (
        AgentAction.objects.filter(
            turn__session=session,
            action_type="submit_candidate",
            validation_status=ValidationStatus.VALID,
        )
        .order_by("pk")
        .values("goal", "args_redacted")[:max_candidates]
    )

    results: list[PriorCandidate] = []
    for action in actions:
        args = action.get("args_redacted") or {}
        results.append(PriorCandidate(
            category=clean_text(args.get("category", "unknown"), limit=80) or "unknown",
            description=clean_text(action.get("goal", ""), limit=200),
        ))
    return results


def extract_hypotheses(session, max_notes: int) -> list[str]:
    notes = (
        session.notes.filter(note_type__in=["hypothesis", "gap"])
        .order_by("pk")
        .values_list("content", flat=True)[:max_notes]
    )
    results = []
    for content in notes:
        if isinstance(content, dict):
            text = content.get("text", "") or content.get("description", "")
        else:
            text = str(content)
        text = clean_text(text, limit=200)
        if text:
            results.append(text)
    return results


def clean_text(value, *, limit: int) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return " ".join(text.split())[:limit]
