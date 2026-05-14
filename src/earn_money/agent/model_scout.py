"""Discover and rank free OpenRouter models per task profile.

Hits GET /models, keeps only free-tier entries, scores each against
the five task profiles using keyword + context-length heuristics, and
returns recommended env-var assignments.

All functions here are pure (no I/O) and fully testable without HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass

from earn_money.agent.task_router import TaskType, profile_env_var

# Scoring rules: (keyword_in_lowercase_model_id, points)
# Keywords are matched as substrings; longest / most specific should
# score higher so a specialist model beats a general one.
_RULES: dict[TaskType, list[tuple[str, int]]] = {
    TaskType.CODING_SECURITY: [
        ("codestral", 5), ("starcoder", 5), ("coder", 4),
        ("code", 2), ("qwen", 1),
    ],
    TaskType.DEEP_REASONING: [
        ("deepseek-r1", 6), ("-r1", 4), (":r1", 4),
        ("reason", 3), ("think", 2), ("deepseek", 2),
    ],
    TaskType.STRUCTURED_EXTRACTION: [
        ("granite", 4), ("nano", 3), ("mini", 2),
        ("small", 2), ("qwen", 1),
    ],
    TaskType.REPORT_WRITING: [
        ("mistral", 3), ("llama", 2), ("wizard", 2), ("gemma", 1),
    ],
    TaskType.DEFAULT_ASSISTANT: [
        ("qwen", 2), ("llama", 2), ("mistral", 2),
        ("gemma", 1), ("phi", 1),
    ],
}

# Context-length bonus: +1 for every full 32 k tokens above the 4 k baseline.
_CTX_BASELINE = 4_096
_CTX_STEP = 32_768


@dataclass(frozen=True)
class ModelInfo:
    """Normalized representation of a single OpenRouter model entry."""

    id: str             # e.g. "qwen/qwen3-235b-a22b:free"
    name: str
    context_length: int


def is_free_model(raw: dict) -> bool:  # type: ignore[type-arg]
    """Return True if the raw model dict represents a free-tier model."""
    if str(raw.get("id", "")).endswith(":free"):
        return True
    pricing = raw.get("pricing") or {}
    return (
        str(pricing.get("prompt", "1")) == "0"
        and str(pricing.get("completion", "1")) == "0"
    )


def parse_models_response(data: dict) -> list[ModelInfo]:  # type: ignore[type-arg]
    """Extract free `ModelInfo` objects from the /models JSON response."""
    models: list[ModelInfo] = []
    for raw in data.get("data", []):
        if not is_free_model(raw):
            continue
        mid = str(raw.get("id", "")).strip()
        if not mid:
            continue
        models.append(
            ModelInfo(
                id=mid,
                name=str(raw.get("name", mid)),
                context_length=int(raw.get("context_length") or 0),
            )
        )
    return models


def score_model(model: ModelInfo, task: TaskType) -> int:
    """Score `model` for `task` using keyword matches + context bonus."""
    mid = model.id.lower()
    score = sum(pts for kw, pts in _RULES.get(task, []) if kw in mid)
    score += max(0, (model.context_length - _CTX_BASELINE) // _CTX_STEP)
    return score


def recommend_profiles(models: list[ModelInfo]) -> dict[str, str]:
    """Return {env_var: model_id} for each task profile + global default.

    Returns an empty dict when `models` is empty.
    """
    if not models:
        return {}

    result: dict[str, str] = {}
    for task in TaskType:
        best = max(models, key=lambda m: score_model(m, task))
        result[profile_env_var(task)] = best.id

    # Global default mirrors the default_assistant pick.
    result["OPENROUTER_DEFAULT_MODEL"] = result[
        profile_env_var(TaskType.DEFAULT_ASSISTANT)
    ]
    return result
