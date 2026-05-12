"""Passive-recon runner. Cron entry point — passive subdomain discovery only."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import dns.resolver
import tldextract  # bundled suffix list; no network fetch needed at import time

from earn_money import config, db, flags, policy, scope
from earn_money.recon import assets, chaos, resolver, subfinder

SubfinderRun = Callable[[str], list[str]]


@dataclass(frozen=True)
class PassiveReconResult:
    subdomains_discovered: int
    assets_upserted: int


def _apexes_from_in_scope(in_scope: list[str]) -> set[str]:
    """Return the set of apex domains (registrable domain + TLD) to feed
    subfinder/chaos. Uses tldextract to handle multi-label TLDs like ``.co.uk``
    correctly: ``api.staging.example.co.uk`` -> ``example.co.uk``.
    """
    apexes: set[str] = set()
    # suffix_list_urls=() forces offline mode — uses only the bundled suffix list,
    # no network fetches during tests or cron runs.
    extract = tldextract.TLDExtract(suffix_list_urls=())
    for entry in in_scope:
        bare = entry.removeprefix("*.").lower()
        parts = extract(bare)
        if parts.domain and parts.suffix:
            apexes.add(f"{parts.domain}.{parts.suffix}")
        else:
            # Fallback: tldextract couldn't parse it (e.g., bare hostname).
            apexes.add(bare)
    return apexes


def _is_in_scope(fqdn: str, in_scope: list[str]) -> bool:
    fqdn = fqdn.lower()
    for entry in in_scope:
        entry_l = entry.lower()
        if entry_l == fqdn:
            return True
        if entry_l.startswith("*."):
            suffix = entry_l[2:]
            if fqdn.endswith("." + suffix) or fqdn == suffix:
                return True
    return False


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    chaos_client: chaos.Client,
    dns_resolver: dns.resolver.Resolver,
    subfinder_run: SubfinderRun = subfinder.enumerate_subdomains,
) -> PassiveReconResult:
    """Run passive recon for one program."""
    flags.require_recon_enabled(paths)
    flags.require_program_not_frozen(paths, platform, slug)

    if platform != "hackerone":
        raise ValueError(f"platform {platform!r} not supported in Phase 2")

    s = scope.read_scope(paths.scope_file(platform, slug))
    policy.require_policy_allows(s, mode="passive")

    apexes = _apexes_from_in_scope(s.in_scope)

    candidates: set[str] = set()
    for apex in sorted(apexes):
        for sub in subfinder_run(apex):
            candidates.add(sub.lower())
        for sub in chaos_client.fetch_subdomains(apex):
            candidates.add(sub.lower())

    in_scope_candidates = sorted(c for c in candidates if _is_in_scope(c, s.in_scope))

    observed_at = datetime.now(UTC).isoformat(timespec="seconds")
    observations: list[assets.AssetObservation] = []
    for sub in in_scope_candidates:
        ips = resolver.resolve_a(sub, dns_resolver=dns_resolver)
        observations.append(assets.AssetObservation(subdomain=sub, ips=tuple(ips)))

    db_path = paths.program_db(platform, slug)
    conn = db.open_db(db_path)
    try:
        summary = assets.upsert_assets(
            conn, observations, observed_at=observed_at, in_scope=True
        )
    finally:
        conn.close()

    return PassiveReconResult(
        subdomains_discovered=len(in_scope_candidates),
        assets_upserted=summary.inserted + summary.updated,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="passive-recon")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--resolver",
        action="append",
        default=None,
        help="Recursive resolver IP (repeat for multiple). Defaults to 1.1.1.1 + 9.9.9.9.",
    )
    args = parser.parse_args(argv)

    nameservers = args.resolver or ["1.1.1.1", "9.9.9.9"]
    paths = config.Paths.from_root(args.root)

    try:
        chaos_token = os.environ.get("CHAOS_API_TOKEN", "")
        chaos_client = chaos.Client(token=chaos_token)
    except chaos.ChaosAPIError as e:
        print(f"passive-recon: {e}", file=sys.stderr)
        return 1

    dns_resolver = resolver.make_default_resolver(nameservers)

    try:
        result = run_program(
            paths, args.platform, args.program,
            chaos_client=chaos_client,
            dns_resolver=dns_resolver,
        )
    except flags.ReconDisabled as e:
        print(f"passive-recon: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"passive-recon: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"passive-recon: {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(
            f"passive-recon: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1
    finally:
        chaos_client.close()

    print(
        f"passive-recon: discovered={result.subdomains_discovered} "
        f"upserted={result.assets_upserted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
