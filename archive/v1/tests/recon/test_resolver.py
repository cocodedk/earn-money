from __future__ import annotations

from unittest.mock import MagicMock

import dns.exception
import dns.resolver

from earn_money.recon import resolver


def test_resolve_returns_a_records() -> None:
    fake_answer = [MagicMock(address="93.184.216.34"), MagicMock(address="93.184.216.35")]
    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = fake_answer

    ips = resolver.resolve_a("www.example.com", dns_resolver=fake_resolver)

    assert sorted(ips) == ["93.184.216.34", "93.184.216.35"]
    fake_resolver.resolve.assert_called_once_with("www.example.com", "A")


def test_resolve_returns_empty_on_nxdomain() -> None:
    fake_resolver = MagicMock()
    fake_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()
    assert resolver.resolve_a("missing.example.com", dns_resolver=fake_resolver) == []


def test_resolve_returns_empty_on_timeout() -> None:
    fake_resolver = MagicMock()
    fake_resolver.resolve.side_effect = dns.exception.Timeout()
    assert resolver.resolve_a("slow.example.com", dns_resolver=fake_resolver) == []


def test_resolve_returns_empty_on_no_answer() -> None:
    fake_resolver = MagicMock()
    fake_resolver.resolve.side_effect = dns.resolver.NoAnswer()
    assert resolver.resolve_a("no-a.example.com", dns_resolver=fake_resolver) == []


def test_make_default_resolver_uses_configured_nameservers() -> None:
    r = resolver.make_default_resolver(["1.1.1.1", "9.9.9.9"])
    assert r.nameservers == ["1.1.1.1", "9.9.9.9"]
    assert r.lifetime == 5.0
