from __future__ import annotations

import ipaddress
from urllib.parse import urljoin, urlparse

from earn_money.agent.roe_profile import RoeProfile

_ALLOWED_SCHEMES = frozenset(["http", "https"])

_PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / IMDS
    ipaddress.ip_network("224.0.0.0/4"),     # multicast
    ipaddress.ip_network("fc00::/7"),        # ULA
    ipaddress.ip_network("fe80::/10"),       # link-local IPv6
]


class ScopeDenied(Exception):
    pass


class ScopePolicy:
    def __init__(self, profile: RoeProfile, base_url: str) -> None:
        self._p = profile
        self._base = base_url.rstrip("/")

    def check(self, url: str) -> str:
        """Resolve and validate *url*. Returns the normalised absolute URL."""
        absolute = self._resolve(url)
        parsed = urlparse(absolute)

        if parsed.scheme not in _ALLOWED_SCHEMES:
            raise ScopeDenied(f"Unsupported scheme: {parsed.scheme!r}")

        host = parsed.hostname or ""
        self._check_host(host)
        self._check_path(parsed.path)

        return absolute

    def check_redirect(self, location: str, current_url: str) -> str:
        """Validate a redirect *location* relative to *current_url*."""
        absolute = urljoin(current_url, location)
        return self.check(absolute)

    # ── private ──────────────────────────────────────────────────────────────

    def _resolve(self, url: str) -> str:
        if url.startswith(("http://", "https://")):
            return url
        return urljoin(self._base + "/", url.lstrip("/"))

    def _check_host(self, host: str) -> None:
        if not host:
            raise ScopeDenied("Empty host")

        # Reject private/loopback/link-local IPs
        try:
            addr = ipaddress.ip_address(host)
            for net in _PRIVATE_NETS:
                if addr in net:
                    raise ScopeDenied(f"Private/reserved IP not allowed: {host}")
        except ValueError:
            pass  # Not an IP address — continue with hostname checks

        if self._p.is_host_denied(host):
            raise ScopeDenied(f"Host is explicitly denied: {host}")

        if not self._p.is_host_allowed(host):
            raise ScopeDenied(f"Host not in scope: {host}")

    def _check_path(self, path: str) -> None:
        if ".." in path.split("/"):
            raise ScopeDenied(f"Path traversal detected: {path}")
