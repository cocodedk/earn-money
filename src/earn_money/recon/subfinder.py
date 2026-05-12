"""Subfinder subprocess wrapper. Passive subdomain enumeration."""

from __future__ import annotations

import subprocess


class SubfinderError(Exception):
    """Raised when subfinder is missing or exits non-zero."""


def enumerate_subdomains(domain: str) -> list[str]:
    """Return a deduplicated list of subdomains for ``domain``.

    Calls ``subfinder -d <domain> -silent -all``. Requires subfinder on PATH.
    Raises ``SubfinderError`` when the binary is missing or exits non-zero.
    """
    try:
        result = subprocess.run(
            ["subfinder", "-d", domain, "-silent", "-all"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SubfinderError(
            "subfinder binary not found on PATH. Install per "
            "https://github.com/projectdiscovery/subfinder."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SubfinderError(
            f"subfinder exited {exc.returncode}: {exc.stderr.strip()}"
        ) from exc

    seen: set[str] = set()
    out: list[str] = []
    for line in result.stdout.splitlines():
        sub = line.strip().lower()
        if sub and sub not in seen:
            seen.add(sub)
            out.append(sub)
    return out
