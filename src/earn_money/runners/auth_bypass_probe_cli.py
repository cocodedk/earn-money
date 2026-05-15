"""CLI entry-point for auth-bypass-probe."""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx

from earn_money import config, flags, policy, roe
from earn_money._time import now_iso
from earn_money.recon import auth_bypass_tool
from earn_money.runners import active, auth_bypass_probe

_HTTP_TIMEOUT = 10.0
_USER_AGENT = "earn-money-authbypass/1.0 (bb@cocode.dk)"


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str,
    auth_testing_authorized: bool = False,
    mutation_testing_authorized: bool = False,
    auth_lockout_budget: int = 0,
    authorized_test_accounts: tuple[str, ...] = (),
    max_requests_per_second: int = 10,
) -> Callable[[list[str]], active.ToolRunResult]:
    # Budget is shared across the entire run, not reset per target.
    budget_remaining = auth_lockout_budget

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        nonlocal budget_remaining
        signals: list[object] = []
        errors = 0
        now = now_iso()
        interval = 1.0 / max_requests_per_second
        with httpx.Client(
            timeout=_HTTP_TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            for url in targets:
                flags.require_recon_enabled(paths)
                flags.require_program_not_frozen(paths, platform, slug)
                try:
                    sigs = auth_bypass_tool.probe_service(
                        url, client=client, run_id=run_id, observed_at=now,
                        auth_testing_authorized=auth_testing_authorized,
                        mutation_testing_authorized=mutation_testing_authorized,
                        auth_lockout_budget=budget_remaining,
                        authorized_test_accounts=authorized_test_accounts,
                        request_interval=interval,
                    )
                    # Deduct the max JWT requests probe_service could have sent.
                    api_count = sum(1 for p in auth_bypass_tool.ADMIN_PATHS if "/api/" in p)
                    write_factor = 2 if mutation_testing_authorized else 1
                    used = min(budget_remaining, api_count * write_factor)
                    budget_remaining = max(0, budget_remaining - used)
                except httpx.HTTPError:
                    errors += 1
                    continue
                signals.extend(sigs)
        return active.ToolRunResult(
            outputs=tuple(signals),
            source_failures=errors,
            raw_stdout=f"auth_bypass_candidates={len(signals)} errors={errors}",
        )
    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auth-bypass-probe")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--max-targets", type=int, default=None)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex

    try:
        program_roe = roe.read_roe(paths.roe_file(args.platform, args.program))
        real_tool = _build_real_tool(
            paths, platform=args.platform, slug=args.program, run_id=run_id,
            auth_testing_authorized=program_roe.auth_testing_authorized,
            mutation_testing_authorized=program_roe.mutation_testing_authorized,
            auth_lockout_budget=program_roe.auth_lockout_budget,
            authorized_test_accounts=tuple(program_roe.authorized_test_accounts),
            max_requests_per_second=program_roe.max_requests_per_second,
        )
        result = auth_bypass_probe.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id, max_targets=args.max_targets,
        )
    except flags.ReconDisabled as e:
        print(f"auth-bypass-probe: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"auth-bypass-probe: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"auth-bypass-probe: {e}", file=sys.stderr)
        return 4
    except roe.InvalidRoE as e:
        print(f"auth-bypass-probe: invalid roe.md: {e}", file=sys.stderr)
        return 6
    except Exception as e:
        print(
            f"auth-bypass-probe: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    if result.prereq_skipped:
        print("auth-bypass-probe: skipped — no recent httpx run; run bin/httpx-probe first")
    else:
        print(
            f"auth-bypass-probe: scanned={result.targets_scanned} "
            f"signals={result.outputs_recorded} "
            f"source_failures={result.source_failures}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
