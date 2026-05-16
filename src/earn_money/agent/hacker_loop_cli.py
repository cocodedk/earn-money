"""CLI for the RoE-controlled LLM probe loop.

Usage: bin/probe-target --platform hackerone --program example \\
         --base-url https://target.example.com --roe-profile roe/example.yaml
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from earn_money import config
from earn_money.agent import providers as providers_mod
from earn_money.agent.budget import RequestBudget
from earn_money.agent.finding_verifier import FindingVerifier
from earn_money.agent.hacker_loop import HackerLoop, LoopResult
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.http_tool import HttpTool
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType, load_roe_profile
from earn_money.agent.scope_policy import ScopePolicy

_SEED_SQL = """
SELECT DISTINCT target
FROM signals
WHERE tool IN ('katana', 'swagger')
LIMIT 100
"""


def _seed_urls(db_path: Path, base_url: str) -> list[str]:
    if not db_path.exists():
        return [base_url]
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(_SEED_SQL).fetchall()
        urls = [row[0] for row in rows if row[0]]
        return urls or [base_url]
    except Exception:
        return [base_url]


def _apply_cli_limits(profile: RoeProfile, args: argparse.Namespace) -> RoeProfile:
    """Return a new profile with CLI limits applied as stricter overrides."""
    overrides: dict[str, object] = {}
    if args.max_turns is not None:
        overrides["max_turns"] = min(profile.max_turns, args.max_turns)
    if args.max_requests is not None:
        overrides["max_requests"] = min(profile.max_requests, args.max_requests)
    if args.max_posts is not None:
        overrides["max_posts"] = min(profile.max_posts, args.max_posts)
    if args.max_response_bytes is not None:
        overrides["max_response_bytes"] = min(profile.max_response_bytes, args.max_response_bytes)
    if not overrides:
        return profile
    data = profile.model_dump(exclude={"source_type", "source_ref"})
    data.update(overrides)
    # Ensure max_posts never exceeds max_requests after overrides
    effective_requests = int(data["max_requests"])
    if int(data["max_posts"]) > effective_requests:
        data["max_posts"] = effective_requests
    return RoeProfile.from_dict(data, profile.source_type, profile.source_ref)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="probe-target")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--program", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--roe-profile", default=None, type=Path)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--max-requests", type=int, default=None)
    parser.add_argument("--max-posts", type=int, default=None)
    parser.add_argument("--max-response-bytes", type=int, default=None)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    # Load and refine RoE profile
    profile = load_roe_profile(args.roe_profile, RoeSourceType.MANUAL)
    profile = _apply_cli_limits(profile, args)

    # Gate checks
    paths = config.Paths.from_root(args.root)
    recon_flag = args.root / "RECON_ENABLED"
    if not recon_flag.exists():
        print("probe-target: RECON_ENABLED not present — pipeline halted", file=sys.stderr)
        return 1

    base_url: str = args.base_url
    db_path = paths.program_db(args.platform, args.program)

    # Wire components
    roe_policy = RoePolicy(profile)
    scope_policy = ScopePolicy(profile, base_url)
    budget = RequestBudget(profile)
    http_tool = HttpTool(base_url, roe_policy, scope_policy, budget)
    session = HackerSession()
    session.seed_urls(_seed_urls(db_path, base_url))
    verifier = FindingVerifier(profile)
    provider = providers_mod.from_env()

    loop = HackerLoop(profile, roe_policy, http_tool, budget, session, verifier, provider)
    result: LoopResult = loop.run()

    _print_result(args, result)
    return 0


def _print_result(args: argparse.Namespace, result: LoopResult) -> None:
    print(
        f"probe-target: {result.turns} turns, "
        f"{len(result.candidate_findings)} candidates, "
        f"{len(result.verified_findings)} verified, "
        f"{len(result.policy_denials)} denials, "
        f"stop={result.stop_reason}",
        flush=True,
    )
    for f in result.verified_findings:
        print(f"  [verified:{f.get('type','?')}] {f.get('path', f.get('target', '?'))}", flush=True)
    for f in result.candidate_findings:
        loc = f.get('path', f.get('target', '?'))
        print(f"  [candidate:{f.get('type','?')}] {loc}", flush=True)
    for d in result.policy_denials:
        print(f"  [denied] {d}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
