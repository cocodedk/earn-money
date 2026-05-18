"""Step registry + decider hook for the active pipeline.

Holds the immutable ordered tuple of `(name, run_program_callable)`
pairs and the `_pick_next` decider dispatch. Extracted from
`active_pipeline` to keep the orchestrator under the 200-line cap.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from earn_money import config
from earn_money.runners import (
    active,
    auth_bypass_probe,
    graphql_probe,
    httpx_probe,
    katana_crawl,
    nuclei_scan,
    sourcemap_scan,
    sqli_probe,
    takeover_validate,
    xss_probe,
)

from ._active_pipeline_steps import StepResult

if TYPE_CHECKING:
    from earn_money.agent.decider import AgentDecider  # type-only; no runtime cycle


# Tuple-of-(name, run_program-callable) keeps step order explicit and
# lets `run_program_pipeline` enumerate them without copy-paste.
_PIPELINE: tuple[tuple[str, Callable[..., active.ActiveRunResult]], ...] = (
    ("httpx-probe", httpx_probe.run_program),
    ("nuclei-scan", nuclei_scan.run_program),
    ("takeover-validate", takeover_validate.run_program),
    ("sourcemap-scan", sourcemap_scan.run_program),
    ("katana-crawl", katana_crawl.run_program),
    ("graphql-probe", graphql_probe.run_program),
    ("auth-bypass-probe", auth_bypass_probe.run_program),
    ("sqli-probe", sqli_probe.run_program),
    ("xss-probe", xss_probe.run_program),
)


_PIPELINE_BY_NAME = dict(_PIPELINE)


def _pick_next(
    pending: list[str],
    completed: list[StepResult],
    paths: config.Paths,
    platform: str,
    slug: str,
    decider: AgentDecider | None,
    default_max_targets: int | None,
) -> tuple[str | None, int | None]:
    """Return (step_name, max_targets) for the next runner, or (None, _)
    to stop the pipeline. With `decider=None`, picks the first pending
    step in fixed order."""
    if not pending:
        return None, None
    if decider is None:
        return pending[0], default_max_targets
    decision = decider(
        paths, platform, slug, completed_steps=tuple(completed),
    )
    if decision.next_step == "stop":
        return None, None
    if decision.next_step not in _PIPELINE_BY_NAME or decision.next_step not in pending:
        # Decider returned an unknown or already-completed step — fall back to
        # the next pending step rather than crashing or looping the pipeline.
        return pending[0], default_max_targets
    return decision.next_step, decision.max_targets or default_max_targets
