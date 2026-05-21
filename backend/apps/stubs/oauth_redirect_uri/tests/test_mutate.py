"""Unit tests for stub 2.14 redirect URI mutation generation."""
from __future__ import annotations
from urllib.parse import urlparse
import pytest
from apps.stubs.oauth_redirect_uri.mutate import generate_mutations, MutationClass


VALID = "https://app.example.test/oauth/callback"
SCANNER = "https://scanner.invalid"


def test_generates_all_mutation_classes():
    mutations = generate_mutations(VALID, SCANNER)
    classes = {m.mutation_class for m in mutations}
    assert MutationClass.FOREIGN_ORIGIN in classes
    assert MutationClass.HOST_SUFFIX in classes
    assert MutationClass.HOST_PREFIX in classes
    assert MutationClass.SCHEME_DOWNGRADE in classes
    assert MutationClass.PATH_PREFIX in classes
    assert MutationClass.PATH_TRAVERSAL in classes
    assert MutationClass.ENCODED_HOST in classes
    assert MutationClass.USERINFO_CONFUSION in classes


def test_count_respects_cap():
    mutations = generate_mutations(VALID, SCANNER, max_probes=4)
    assert len(mutations) <= 4


def test_foreign_origin_uses_scanner_origin():
    mutations = generate_mutations(VALID, SCANNER)
    foreign = next(m for m in mutations if m.mutation_class == MutationClass.FOREIGN_ORIGIN)
    assert urlparse(foreign.mutated_uri).netloc == "scanner.invalid"


def test_scheme_downgrade_uses_http():
    mutations = generate_mutations(VALID, SCANNER)
    downgrade = next(m for m in mutations if m.mutation_class == MutationClass.SCHEME_DOWNGRADE)
    assert downgrade.mutated_uri.startswith("http://")


def test_mutations_preserve_state():
    mutations = generate_mutations(VALID, SCANNER)
    for m in mutations:
        assert m.mutation_class is not None
        assert m.mutated_uri


def test_invalid_baseline_returns_empty():
    mutations = generate_mutations("not-a-url", SCANNER)
    assert mutations == []
