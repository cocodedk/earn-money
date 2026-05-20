from __future__ import annotations

import hashlib
import unittest

from ..hashing import body_hash, body_hash_bytes, prefixed_body_hash


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


class BodyHashBytesTests(unittest.TestCase):
    def test_raw_hex_sha256_of_bytes(self) -> None:
        # Bytes-typed flavour for callers that have wire bytes
        # already (stub 1.15 fetcher slices response.content before
        # decoding, so hashing the decoded str would re-encode and
        # also mishash on `errors="replace"` substitutions).
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert body_hash_bytes(data) == expected

    def test_empty_bytes(self) -> None:
        assert body_hash_bytes(b"") == hashlib.sha256(b"").hexdigest()

    def test_non_utf8_bytes(self) -> None:
        # The whole point of the bytes flavour: hash raw wire data
        # regardless of whether it's valid text.
        data = b"\xff\xfe\x00\x01"
        assert body_hash_bytes(data) == hashlib.sha256(data).hexdigest()


class PrefixedBodyHashTests(unittest.TestCase):
    def test_prefix_format(self) -> None:
        assert prefixed_body_hash("abc").startswith("sha256:")

    def test_hex_after_prefix_matches_body_hash(self) -> None:
        # The prefix variant wraps body_hash — splitting on `:` must
        # recover the raw hex.
        text = "evidence body"
        prefixed = prefixed_body_hash(text)
        assert prefixed == f"sha256:{body_hash(text)}"
