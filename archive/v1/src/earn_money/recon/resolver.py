"""DNS resolution. A-record only in Phase 2."""

from __future__ import annotations

import dns.exception
import dns.resolver


def make_default_resolver(nameservers: list[str]) -> dns.resolver.Resolver:
    """Return a Resolver configured to use the given recursive resolvers.

    Use a dedicated resolver (e.g. ``1.1.1.1`` on the VPS, or a self-hosted
    Unbound) — not the ISP default — to avoid leaking enumeration patterns.
    """
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = list(nameservers)
    r.lifetime = 5.0
    return r


def resolve_a(host: str, *, dns_resolver: dns.resolver.Resolver) -> list[str]:
    """Return A-record IPs for ``host``. Empty list on NXDOMAIN/timeout/no-answer."""
    try:
        answer = dns_resolver.resolve(host, "A")
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.exception.Timeout,
        dns.resolver.NoNameservers,
    ):
        return []
    return [rdata.address for rdata in answer]
