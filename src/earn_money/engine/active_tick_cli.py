"""CLI entry-point for the active-pipeline orchestrator.

Wires `active_pipeline.run_program_pipeline` to the real per-runner
`_build_real_tool` factories. With `--program X`, runs the pipeline
once for that program; without it, iterates every registered program
and runs the pipeline for each.

Honors `RECON_ENABLED` and per-program `FROZEN` flags transparently
because each runner's gate is re-checked by the orchestrator.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from earn_money import config
from earn_money.engine import active_pipeline
from earn_money.registry import iter_registered_programs
from earn_money.runners import (
    graphql_probe_cli,
    httpx_probe_cli,
    katana_crawl_cli,
    nuclei_scan_cli,
    sourcemap_scan_cli,
    takeover_validate_cli,
)


def _real_tool_factory(
    runner: str, paths: config.Paths, platform: str, slug: str, run_id: str,
) -> active_pipeline.ToolRun:
    if runner == "httpx-probe":
        return httpx_probe_cli._build_real_tool(paths, platform, slug, run_id)
    if runner == "nuclei-scan":
        return nuclei_scan_cli._build_real_tool(paths, platform, slug, run_id)
    if runner == "takeover-validate":
        rate = takeover_validate_cli.resolve_rate_limit(paths, platform, slug)
        concurrency = takeover_validate_cli.resolve_subzy_concurrency(rate)
        return takeover_validate_cli._build_real_tool(
            paths, platform, slug, run_id, concurrency=concurrency,
        )
    if runner == "sourcemap-scan":
        return sourcemap_scan_cli._build_real_tool(paths, platform, slug, run_id)
    if runner == "katana-crawl":
        return katana_crawl_cli._build_real_tool(paths, platform, slug, run_id)
    if runner == "graphql-probe":
        return graphql_probe_cli._build_real_tool(paths, platform, slug, run_id)
    raise ValueError(f"unknown runner {runner!r}")


def _print_pipeline_result(result: active_pipeline.PipelineResult) -> None:
    slug = f"{result.platform}/{result.slug}"
    if result.aborted_reason is not None:
        print(f"active-tick: {slug} aborted: {result.aborted_reason}")
        return
    print(f"active-tick: {slug} —")
    for step in result.steps:
        marker = {"ok": "✓", "skipped": "·", "failed": "✗"}.get(step.status, "?")
        detail = f" ({step.detail})" if step.detail else ""
        outputs = f" outputs={step.outputs_recorded}" if step.outputs_recorded else ""
        print(f"  {marker} {step.runner}{outputs}{detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="active-tick")
    parser.add_argument("--platform", default=None,
                        help="restrict to one platform (e.g. hackerone)")
    parser.add_argument("--program", default=None,
                        help="restrict to one program slug")
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--max-targets", type=int, default=None,
                        help="per-step target cap (passes through to each runner)")
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    targets = list(iter_registered_programs(paths))
    if args.platform is not None:
        targets = [(p, s) for p, s in targets if p == args.platform]
    if args.program is not None:
        targets = [(p, s) for p, s in targets if s == args.program]
    if not targets:
        print("active-tick: no matching programs", file=sys.stderr)
        return 1

    any_failure = False
    for platform, slug in targets:
        try:
            result = active_pipeline.run_program_pipeline(
                paths, platform, slug,
                tool_factory=_real_tool_factory,
                max_targets_per_step=args.max_targets,
            )
        except Exception as exc:
            print(
                f"active-tick: {platform}/{slug} unexpected error: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            any_failure = True
            continue
        _print_pipeline_result(result)
        if any(s.status == "failed" for s in result.steps):
            any_failure = True

    return 1 if any_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
