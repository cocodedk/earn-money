"""CLI: resolve a URL to a registered (platform, slug) pair via scope lookup.

Prints "<platform> <slug>" to stdout on success; exits non-zero if the host
is not in scope for any registered program.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from earn_money.config import Paths
from earn_money.registry import iter_registered_programs
from earn_money.scope import is_in_scope, read_scope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resolve-target")
    parser.add_argument("url", help="Target URL (e.g. https://target.cocode.dk/#/)")
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    host = urlparse(args.url).hostname or ""
    if not host:
        print(f"resolve-target: cannot parse hostname from {args.url!r}", file=sys.stderr)
        return 1

    paths = Paths.from_root(args.root)
    for platform, slug in iter_registered_programs(paths):
        s = read_scope(paths.scope_file(platform, slug))
        if is_in_scope(host, s.in_scope, s.out_of_scope):
            print(f"{platform} {slug}")
            return 0

    print(f"resolve-target: {host!r} not in scope for any registered program", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
