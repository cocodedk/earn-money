"""Contract tests for `_shared/auth/token_analysis`.

Pure logic, no I/O. Used by stubs 2.5 / 2.12 to classify a sample
of tokens (reset tokens, recovery codes) as predictable or random.
"""
from __future__ import annotations

import secrets

import pytest

from apps.stubs._shared.auth.token_analysis import (
    TokenAnalysis, analyse_tokens,
)


def _strong_uuids(n: int = 8) -> list[str]:
    """Real UUIDs, the gold standard for random tokens."""
    import uuid
    return [str(uuid.uuid4()) for _ in range(n)]


def _strong_hex(n: int = 8) -> list[str]:
    return [secrets.token_hex(16) for _ in range(n)]


# ----- empty / undersized samples ----------------------------------

def test_empty_sample_returns_inconclusive() -> None:
    out = analyse_tokens([])
    assert out.verdict == "inconclusive"


def test_single_token_returns_inconclusive() -> None:
    out = analyse_tokens(["abc123"])
    assert out.verdict == "inconclusive"


# ----- sequential integer tokens (CRITICAL) -------------------------

def test_sequential_integer_tokens_classified_critical() -> None:
    tokens = [str(n) for n in range(1001, 1009)]
    out = analyse_tokens(tokens)
    assert out.verdict == "predictable"
    assert out.signal == "sequential_integer"
    assert out.severity == "critical"


def test_sequential_with_prefix_classified_critical() -> None:
    """Real-world predictable scheme: prefix + counter."""
    tokens = [f"rt-{n:06d}" for n in range(42, 50)]
    out = analyse_tokens(tokens)
    assert out.verdict == "predictable"
    assert out.signal == "sequential_integer"


def test_non_sequential_integers_not_flagged() -> None:
    """Random integers SHOULD NOT trigger the sequential check."""
    tokens = ["1001", "8273", "4521", "9988", "1212", "5544", "7777", "3333"]
    out = analyse_tokens(tokens)
    assert out.signal != "sequential_integer"


# ----- shared-prefix detection (MEDIUM) ----------------------------

def test_shared_long_prefix_classified_medium() -> None:
    """All tokens begin with the same 16-char prefix → server is
    embedding a constant (e.g. timestamp / user-id) → MEDIUM."""
    common = "2026052100000000"
    tokens = [common + secrets.token_hex(4) for _ in range(8)]
    out = analyse_tokens(tokens)
    assert out.verdict == "predictable"
    assert out.signal == "shared_prefix"
    assert out.severity == "medium"


# ----- low Shannon entropy (HIGH) ----------------------------------

def test_low_entropy_tokens_classified_high() -> None:
    """All tokens drawn from a tiny alphabet — entropy per char is
    < 3 bits — HIGH. Tokens chosen so neither sequential-integer
    nor shared-prefix fires."""
    tokens = [
        "aabbabba", "babaabab", "abbabaab", "bababbaa",
        "aabbbaab", "bbaaaabb", "ababaaba", "babbabab",
    ]
    out = analyse_tokens(tokens)
    assert out.verdict == "predictable"
    assert out.signal == "low_entropy"
    assert out.severity == "high"


# ----- strong tokens: random hex + UUID (no finding) ---------------

def test_strong_uuids_pass_as_random() -> None:
    out = analyse_tokens(_strong_uuids(8))
    assert out.verdict == "random"
    assert out.severity == "info"


def test_strong_hex_tokens_pass_as_random() -> None:
    out = analyse_tokens(_strong_hex(8))
    assert out.verdict == "random"


# ----- result shape -------------------------------------------------

def test_result_is_frozen_dataclass() -> None:
    out = analyse_tokens(_strong_uuids(3))
    with pytest.raises(Exception):
        out.verdict = "predictable"  # type: ignore[misc]


def test_result_carries_sample_count() -> None:
    tokens = _strong_uuids(5)
    out = analyse_tokens(tokens)
    assert out.sample_size == 5


def test_result_carries_entropy_bits_per_char() -> None:
    out = analyse_tokens(_strong_hex(8))
    # hex tokens have ~4 bits / char (16 symbols, log2(16)=4).
    assert 3.5 <= out.entropy_bits_per_char <= 4.1


# ----- internal helper edge cases -----------------------------------

def test_sequential_check_false_when_multiple_prefixes() -> None:
    """Tokens with different prefixes (rt-1 vs tok-2) are not sequential.
    Exercises line 103: len(prefixes) != 1 → return False."""
    from apps.stubs._shared.auth.token_analysis import _is_sequential_integer
    assert _is_sequential_integer(["rt-1", "tok-2", "rt-3"]) is False


def test_longest_common_prefix_empty_list() -> None:
    """_longest_common_prefix([]) returns '' — exercises line 111."""
    from apps.stubs._shared.auth.token_analysis import _longest_common_prefix
    assert _longest_common_prefix([]) == ""


def test_longest_common_prefix_one_token_is_prefix_of_all() -> None:
    """When shortest token is a prefix of all others, the full shortest
    token is returned — exercises line 116 (return shortest)."""
    from apps.stubs._shared.auth.token_analysis import _longest_common_prefix
    # "abc" is a prefix of all three; no char mismatch found in the loop
    assert _longest_common_prefix(["abc", "abcd", "abcde"]) == "abc"


def test_entropy_zero_when_all_tokens_empty() -> None:
    """_entropy_bits_per_char([]) returns 0.0 when joined text is empty —
    exercises line 123."""
    from apps.stubs._shared.auth.token_analysis import _entropy_bits_per_char
    assert _entropy_bits_per_char([""]) == 0.0
