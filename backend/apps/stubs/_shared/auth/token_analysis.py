"""Classify a sample of tokens as predictable vs random.

Pure logic, no I/O. Used by stubs 2.5 (reset tokens) and 2.12
(recovery codes) — both collect N tokens and need a deterministic
classification.

Three checks, in order:
1. **Sequential integers** — the integer suffix increments by 1
   across consecutive tokens (e.g. `rt-1001 / rt-1002 / rt-1003`).
   Worst case: trivial token-guessing → severity=critical.
2. **Shared prefix** — every token begins with ≥16 identical chars
   (timestamp, user-id, salt). Token is partially predictable →
   severity=medium.
3. **Low Shannon entropy** — entropy per char < 3 bits.
   severity=high.

If none fires → random / info.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal


_INT_SUFFIX_RE = re.compile(r"^(?P<prefix>.*?)(?P<num>\d+)$")
_PREFIX_THRESHOLD = 16
_ENTROPY_BPC_LOW = 3.0
_MIN_SAMPLE = 3


Verdict = Literal["random", "predictable", "inconclusive"]
Signal = Literal[
    "none", "sequential_integer", "shared_prefix",
    "low_entropy",
]
Severity = Literal["info", "low", "medium", "high", "critical"]


@dataclass(frozen=True)
class TokenAnalysis:
    """Result of `analyse_tokens()`. `verdict` is the operator-
    facing decision; `signal` + `severity` map to Finding fields."""
    verdict: Verdict
    signal: Signal
    severity: Severity
    sample_size: int
    entropy_bits_per_char: float
    shared_prefix_len: int


def analyse_tokens(tokens: list[str]) -> TokenAnalysis:
    """Classify a sample of reset tokens / recovery codes."""
    n = len(tokens)
    if n < _MIN_SAMPLE:
        return TokenAnalysis(
            verdict="inconclusive", signal="none", severity="info",
            sample_size=n, entropy_bits_per_char=0.0,
            shared_prefix_len=0,
        )
    if _is_sequential_integer(tokens):
        return TokenAnalysis(
            verdict="predictable", signal="sequential_integer",
            severity="critical", sample_size=n,
            entropy_bits_per_char=_entropy_bits_per_char(tokens),
            shared_prefix_len=len(_longest_common_prefix(tokens)),
        )

    shared_len = len(_longest_common_prefix(tokens))
    bpc = _entropy_bits_per_char(tokens)
    if shared_len >= _PREFIX_THRESHOLD:
        return TokenAnalysis(
            verdict="predictable", signal="shared_prefix",
            severity="medium", sample_size=n,
            entropy_bits_per_char=bpc, shared_prefix_len=shared_len,
        )
    if bpc < _ENTROPY_BPC_LOW:
        return TokenAnalysis(
            verdict="predictable", signal="low_entropy",
            severity="high", sample_size=n,
            entropy_bits_per_char=bpc, shared_prefix_len=shared_len,
        )
    return TokenAnalysis(
        verdict="random", signal="none", severity="info",
        sample_size=n, entropy_bits_per_char=bpc,
        shared_prefix_len=shared_len,
    )


def _is_sequential_integer(tokens: list[str]) -> bool:
    """True iff every token decomposes into <same-prefix><int> AND
    the integers are strictly consecutive."""
    parsed: list[tuple[str, int]] = []
    for tok in tokens:
        m = _INT_SUFFIX_RE.match(tok)
        if m is None:
            return False
        parsed.append((m.group("prefix"), int(m.group("num"))))
    prefixes = {p for p, _ in parsed}
    if len(prefixes) != 1:
        return False
    nums = [n for _, n in parsed]
    return all(b - a == 1 for a, b in zip(nums, nums[1:]))


def _longest_common_prefix(tokens: list[str]) -> str:
    """Return the longest string prefix shared by every token."""
    if not tokens:
        return ""
    shortest = min(tokens, key=len)
    for i, ch in enumerate(shortest):
        if any(t[i] != ch for t in tokens):
            return shortest[:i]
    return shortest


def _entropy_bits_per_char(tokens: list[str]) -> float:
    """Shannon entropy across the concatenated token sample."""
    text = "".join(tokens)
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum(
        (c / total) * math.log2(c / total) for c in counts.values()
    )
