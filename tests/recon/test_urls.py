"""Unit tests for the shared target_host helper."""

from __future__ import annotations

from earn_money.recon import urls


def test_target_host_extracts_hostname_from_url() -> None:
    assert urls.target_host("https://api.example.com/foo", "fallback") == "api.example.com"


def test_target_host_strips_port() -> None:
    assert urls.target_host("http://api.example.com:8080/", "fb") == "api.example.com"


def test_target_host_falls_back_when_no_scheme() -> None:
    assert urls.target_host("api.example.com/path", "fb") == "fb"


def test_target_host_falls_back_when_empty() -> None:
    assert urls.target_host("", "fb") == "fb"


def test_target_host_falls_back_when_url_lacks_hostname() -> None:
    """e.g. 'http:///foo' has no hostname — fall back."""
    assert urls.target_host("http:///foo", "fb") == "fb"
