"""Scope-sync runner. Hourly cron entry point."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from earn_money import config, flags, scope
from earn_money._time import now_iso
from earn_money.platforms import hackerone

Action = Literal["unchanged", "updated", "frozen"]


@dataclass(frozen=True)
class SyncResult:
    action: Action
    detail: str


def sync_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    client: hackerone.Client,
) -> SyncResult:
    """Sync a program's scope.md against the platform API.

    Note: this runner is intentionally NOT gated by ``scope.policy``. Scope
    sync only hits the platform's API (e.g. HackerOne), never the target
    assets, so it is safe for all three policy tiers — including
    ``manual-only``, where the spec explicitly allows scope.md maintenance.
    Active recon runners that generate target traffic (Phase 2+) MUST
    enforce ``policy != "manual-only"`` themselves.
    """
    flags.require_recon_enabled(paths)
    flags.require_program_not_frozen(paths, platform, slug)

    if platform != "hackerone":
        raise ValueError(f"platform {platform!r} not supported in Phase 1")

    current = scope.read_scope(paths.scope_file(platform, slug))
    fetched_in, fetched_oos = client.fetch_structured_scope(slug)
    fetched = replace(
        current,
        in_scope=fetched_in,
        out_of_scope=fetched_oos,
        scope_hash="",  # recomputed below
    )
    new_hash = scope.compute_hash(fetched)
    timestamp = now_iso()

    if new_hash == current.scope_hash:
        scope.write_scope(
            paths.scope_file(platform, slug),
            replace(current, last_synced=timestamp),
        )
        return SyncResult("unchanged", "scope hash unchanged")

    removed_in_scope = sorted(set(current.in_scope) - set(fetched_in))
    if removed_in_scope and current.scope_hash:
        reason = (
            "Destructive scope diff: assets removed from in-scope. "
            f"Removed: {', '.join(removed_in_scope)}. "
            "Operator must verify before resuming."
        )
        flags.freeze_program(paths, platform, slug, reason=reason)
        return SyncResult("frozen", reason)

    scope.write_scope(
        paths.scope_file(platform, slug),
        replace(fetched, scope_hash=new_hash, last_synced=timestamp),
    )
    return SyncResult("updated", f"scope updated, hash={new_hash[:12]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scope-sync")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True, help="program slug")
    parser.add_argument(
        "--root",
        default=Path.cwd(),
        type=Path,
        help="repository root (defaults to CWD)",
    )
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)

    try:
        flags.require_recon_enabled(paths)
        flags.require_program_not_frozen(paths, args.platform, args.program)
    except flags.ReconDisabled as e:
        print(f"scope-sync: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"scope-sync: {e}", file=sys.stderr)
        return 3

    if args.platform != "hackerone":
        print(f"scope-sync: platform {args.platform!r} has no sync adapter — skipping")
        return 0

    client: hackerone.Client | None = None
    try:
        client = hackerone.Client(
            username=os.environ.get("HACKERONE_API_USERNAME", ""),
            token=os.environ.get("HACKERONE_API_TOKEN", ""),
        )
        result = sync_program(paths, args.platform, args.program, client)
    except flags.ReconDisabled as e:
        print(f"scope-sync: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"scope-sync: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        # Spec line 103: any sync failure freezes the program.
        try:
            flags.freeze_program(
                paths, args.platform, args.program,
                reason=f"scope-sync failed: {type(e).__name__}: {e}",
            )
        except Exception as freeze_exc:
            print(
                f"scope-sync: also failed to write freeze flag: {freeze_exc}",
                file=sys.stderr,
            )
        print(f"scope-sync: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()
    print(f"scope-sync: {result.action} — {result.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
