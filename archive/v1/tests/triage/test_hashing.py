from __future__ import annotations

import pytest

from earn_money.triage import hashing


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("HTTPS://API.Example.COM/Path", "https://api.example.com/Path"),
        ("https://api.example.com:443/", "https://api.example.com/"),
        ("http://api.example.com:80/foo", "http://api.example.com/foo"),
        ("https://api.example.com:8443/foo", "https://api.example.com:8443/foo"),
        ("https://api.example.com//a/./b/../c/", "https://api.example.com/a/c"),
        ("https://api.example.com/", "https://api.example.com/"),
        ("https://api.example.com/foo#bar", "https://api.example.com/foo"),
        ("https://api.example.com/?b=2&a=1", "https://api.example.com/?a=1&b=2"),
        ("https://api.example.com/?empty=&kept=1", "https://api.example.com/?kept=1"),
        ("https://api.example.com/?debug", "https://api.example.com/?debug"),
    ],
)
def test_normalize_target_rules(raw: str, expected: str) -> None:
    assert hashing.normalize_target(raw) == expected


def test_normalize_asset_is_host_only() -> None:
    assert hashing.normalize_asset("API.Example.COM") == "api.example.com"
    assert hashing.normalize_asset("https://API.Example.COM/foo") == "api.example.com"


def test_normalize_target_non_url_falls_back_to_asset() -> None:
    assert hashing.normalize_target("API.Example.COM") == "api.example.com"


def test_compute_hash_is_stable_across_equivalent_inputs() -> None:
    a = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-2023-1234",
        asset="API.Example.COM", target="HTTPS://API.Example.COM:443/foo#anchor",
        signature="cve-2023-1234|primary|",
    )
    b = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-2023-1234",
        asset="api.example.com", target="https://api.example.com/foo",
        signature="cve-2023-1234|primary|",
    )
    assert a == b


def test_compute_hash_differs_when_vuln_class_differs() -> None:
    a = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="xss-reflected",
        asset="api.example.com", target="https://api.example.com/", signature="sig",
    )
    b = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="open-redirect",
        asset="api.example.com", target="https://api.example.com/", signature="sig",
    )
    assert a != b


def test_compute_hash_differs_when_signature_differs() -> None:
    a = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="x",
        asset="api.example.com", target="https://api.example.com/", signature="sig-a",
    )
    b = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="x",
        asset="api.example.com", target="https://api.example.com/", signature="sig-b",
    )
    assert a != b


def test_compute_hash_changes_on_each_field_independently() -> None:
    """Changing exactly one field must change the hash."""
    base = dict(
        platform="hackerone", slug="example", vuln_class="cve-2023-1234",
        asset="api.example.com", target="https://api.example.com/",
        signature="cve-2023-1234|primary|",
    )
    base_hash = hashing.compute_hash(**base)  # type: ignore[arg-type]
    for field in ["platform", "slug", "vuln_class", "asset", "target", "signature"]:
        variant = {**base, field: base[field] + "_x"}  # type: ignore[operator]
        assert hashing.compute_hash(**variant) != base_hash, (  # type: ignore[arg-type]
            f"hash did not change when {field!r} was mutated"
        )


def test_compute_hash_stable_across_normalization_variants() -> None:
    """Inputs that are semantically equivalent must hash to the same value."""
    canonical = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="api.example.com", target="https://api.example.com/", signature="sig",
    )
    assert hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="API.Example.COM", target="https://API.Example.com:443/", signature="sig",
    ) == canonical
    assert hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="api.example.com", target="https://api.example.com:443/", signature="sig",
    ) == canonical
    h_sorted = hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="api.example.com",
        target="https://api.example.com/?a=1&b=2", signature="sig",
    )
    assert hashing.compute_hash(
        platform="hackerone", slug="example", vuln_class="cve-x",
        asset="api.example.com",
        target="https://api.example.com/?b=2&a=1", signature="sig",
    ) == h_sorted


def test_signature_for_nuclei_normalizes_extracted() -> None:
    sig = hashing.signature_for_nuclei(
        template_id="cve-2023-1234", matcher_name="status-200",
        extracted="HTTPS://API.Example.COM/Foo",
    )
    assert sig == "cve-2023-1234|status-200|https://api.example.com/Foo"


def test_signature_for_nuclei_handles_missing_fields() -> None:
    sig = hashing.signature_for_nuclei(
        template_id="cve-x", matcher_name=None, extracted=None,
    )
    assert sig == "cve-x||"


def test_signature_for_httpx_anomaly_hashes_fingerprints() -> None:
    sig = hashing.signature_for_httpx_anomaly(
        signal_type="server_changed",
        old_fingerprint="nginx/1.18",
        new_fingerprint="nginx/1.20",
    )
    parts = sig.split("|")
    assert parts[0] == "server_changed"
    assert len(parts[1]) == 12
    assert len(parts[2]) == 12
    assert parts[1] != parts[2]
