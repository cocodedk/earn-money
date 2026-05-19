from __future__ import annotations

import hashlib
import unittest

from ..hashing import body_hash, prefixed_body_hash


class BodyHashTests(unittest.TestCase):
    def test_raw_hex_sha256(self) -> None:
        text = "hello world"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert body_hash(text) == expected

    def test_empty_string(self) -> None:
        assert body_hash("") == hashlib.sha256(b"").hexdigest()

    def test_unicode_handled(self) -> None:
        # UTF-8 encoding must be consistent so cross-run hashes match.
        text = "café — élève"
        assert body_hash(text) == hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()


class PrefixedBodyHashTests(unittest.TestCase):
    def test_prefix_format(self) -> None:
        assert prefixed_body_hash("abc").startswith("sha256:")

    def test_hex_after_prefix_matches_body_hash(self) -> None:
        # The prefix variant wraps body_hash — splitting on `:` must
        # recover the raw hex.
        text = "evidence body"
        prefixed = prefixed_body_hash(text)
        assert prefixed == f"sha256:{body_hash(text)}"
