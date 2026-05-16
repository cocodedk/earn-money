### File 1: `pentest_tools/llm/task_router.py` (FIXED)

```python
"""Task router for pentesting LLM operations — fixed for offensive security."""

from enum import Enum
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Task types that map to different model profiles."""
    
    # General
    DEFAULT_ASSISTANT = "default_assistant"
    
    # Pentesting core
    PENTEST_LOOP = "pentest_loop"              # Main attack loop turns
    AGENT_PLANNING = "agent_planning"           # Planning next moves
    DEEP_REASONING = "deep_reasoning"           # Multi-hop chain-of-thought
    
    # Specialized analysis
    CODE_ANALYSIS = "code_analysis"             # JavaScript/HTML/response analysis
    STRUCTURED_EXTRACTION = "structured_extraction"  # Finding extraction
    EXPLOIT_REASONING = "exploit_reasoning"     # Exploit chain reasoning
    
    # Output
    REPORT_WRITING = "report_writing"           # Drafting findings
    EVIDENCE_SUMMARY = "evidence_summary"       # Summarizing observations


# Model recommendations for pentesting (OpenRouter IDs)
PENTEST_MODEL_RECOMMENDATIONS = {
    TaskType.PENTEST_LOOP: [
        "deepseek/deepseek-r1",           # Best: chain-of-thought reasoning
        "qwen/qwen3-235b-a22b",           # Good: strong instruction following
        "anthropic/claude-3-haiku",       # Fast: quick decisions
    ],
    TaskType.AGENT_PLANNING: [
        "deepseek/deepseek-r1",           # Multi-step planning
        "qwen/qwen3-235b-a22b",
    ],
    TaskType.DEEP_REASONING: [
        "deepseek/deepseek-r1",           # Built for this
        "anthropic/claude-3-opus",        # Expensive but excellent
    ],
    TaskType.CODE_ANALYSIS: [
        "qwen/qwen3-coder",               # Code-specialized
        "deepseek/deepseek-coder",
    ],
    TaskType.STRUCTURED_EXTRACTION: [
        "qwen/qwen3-235b-a22b",           # Good at JSON
        "ibm/granite-3-8b-instruct",     # Schema-capable
    ],
    TaskType.EXPLOIT_REASONING: [
        "deepseek/deepseek-r1",           # Reasoning-heavy
    ],
    TaskType.REPORT_WRITING: [
        "mistralai/mistral-small",        # Good prose
        "anthropic/claude-3-haiku",
    ],
    TaskType.DEFAULT_ASSISTANT: [
        "mistralai/mistral-small",        # General purpose
    ],
}


def coerce_task(task: str) -> TaskType:
    """Map a task string to a TaskType, with proper pentesting mappings.
    
    The original bug: "agent_planning" wasn't mapped and fell through
    to DEFAULT_ASSISTANT. Fixed now.
    """
    # Direct string-to-enum mapping
    task_map = {
        "agent_planning": TaskType.AGENT_PLANNING,
        "pentest_loop": TaskType.PENTEST_LOOP,
        "deep_reasoning": TaskType.DEEP_REASONING,
        "code_analysis": TaskType.CODE_ANALYSIS,
        "structured_extraction": TaskType.STRUCTURED_EXTRACTION,
        "exploit_reasoning": TaskType.EXPLOIT_REASONING,
        "report_writing": TaskType.REPORT_WRITING,
        "evidence_summary": TaskType.EVIDENCE_SUMMARY,
        "default_assistant": TaskType.DEFAULT_ASSISTANT,
    }
    
    # Try exact match first
    if task in task_map:
        return task_map[task]
    
    # Try enum value match
    try:
        return TaskType(task)
    except ValueError:
        logger.warning(f"Unknown task type '{task}', falling back to DEFAULT_ASSISTANT")
        return TaskType.DEFAULT_ASSISTANT


def resolve_model(task: TaskType, provider: str = "openrouter") -> str:
    """Resolve which model to use for a given task type.
    
    Resolution order:
    1. Task-specific env var: OPENROUTER_MODEL_<TASK_NAME>
    2. Provider default: OPENROUTER_DEFAULT_MODEL
    3. Hardcoded recommendation (first in list)
    4. Raise RouterUnconfigured
    """
    if provider != "openrouter":
        # Non-OpenRouter providers handle their own model selection
        return os.getenv("LLM_DEFAULT_MODEL", "")
    
    # Try task-specific env var
    env_var = f"OPENROUTER_MODEL_{task.name.upper()}"
    model = os.getenv(env_var)
    if model:
        logger.debug(f"Resolved {task} → {model} (from {env_var})")
        return model
    
    # Try global default
    model = os.getenv("OPENROUTER_DEFAULT_MODEL")
    if model:
        logger.debug(f"Resolved {task} → {model} (from OPENROUTER_DEFAULT_MODEL)")
        return model
    
    # Try hardcoded recommendations
    recommendations = PENTEST_MODEL_RECOMMENDATIONS.get(task, [])
    if recommendations:
        model = recommendations[0]
        logger.warning(
            f"No model configured for {task}. "
            f"Using recommended: {model}. "
            f"Set {env_var} or OPENROUTER_DEFAULT_MODEL to override."
        )
        return model
    
    raise RouterUnconfigured(
        f"No model configured for task '{task}'. "
        f"Set {env_var} or OPENROUTER_DEFAULT_MODEL."
    )


class RouterUnconfigured(Exception):
    """Raised when no model can be resolved for a task."""
    pass
```

