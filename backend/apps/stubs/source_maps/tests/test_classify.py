"""Tests for the source-maps classifier (stub 1.14 slice 6).

`classify_map_result(...)` composes outputs from prior slices into a
single Verdict per (asset, map) pair, mapping the spec's §Classification,
§Confidence rules, and §Finding status rules into one place.
"""
from __future__ import annotations

import unittest

from ..classify import Verdict, classify_map_result
from ..fetcher import FetchOutcome
from ..resolver import ResolvedMapUrl
from ._classify_factories import (
    metadata as _metadata,
    ok_asset as _ok_asset,
    ok_map as _ok_map,
    resolved_ok as _resolved_ok,
)


_BASE = "https://example.test"


class ConfirmedFindingTests(unittest.TestCase):
    def test_comment_reference_confirmed_high_confidence(self) -> None:
        # Spec §Confidence: high when an explicit sourceMappingURL
        # comment points to an accessible valid map.
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=_ok_map(), metadata=_metadata(),
            reference_type="comment",
        )
        assert v.finding_status == "confirmed"
        assert v.confidence == "high"
        assert v.severity == "info"
        assert v.map_reference_type == "comment"

    def test_fallback_reference_confirmed_medium_confidence(self) -> None:
        # Spec §Confidence: medium when the fallback `.map` probe
        # finds a valid map but no comment was present in the asset.
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=_ok_map(), metadata=_metadata(),
            reference_type="fallback",
        )
        assert v.finding_status == "confirmed"
        assert v.confidence == "medium"
        assert v.map_reference_type == "fallback"

    def test_sources_content_raises_severity_to_low(self) -> None:
        # Spec §Severity: raise to `low` when accessible valid map
        # contains sourcesContent OR clear internal source paths.
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=_ok_map(),
            metadata=_metadata(has_sources_content=True),
            reference_type="comment",
        )
        assert v.severity == "low"
        assert "sources_content_exposed" in v.indicators

    def test_internal_paths_raise_severity_to_low(self) -> None:
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=_ok_map(),
            metadata=_metadata(internal_path_indicators=("/src/",)),
            reference_type="comment",
        )
        assert v.severity == "low"
        assert "internal_path_indicators_present" in v.indicators

    def test_confirmed_indicators_include_reference_type(self) -> None:
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=_ok_map(), metadata=_metadata(),
            reference_type="comment",
        )
        assert "valid_source_map" in v.indicators


class InlineDataUrlTests(unittest.TestCase):
    def test_inline_data_url_yields_candidate_no_fetch(self) -> None:
        # Spec §Source map reference detection: do NOT decode data:
        # maps. Emit a candidate finding with low confidence and the
        # inline_data_url reference type.
        v = classify_map_result(
            asset_outcome=_ok_asset(),
            resolved=ResolvedMapUrl(
                kind="inline_data_url", absolute_url=None,
            ),
            map_outcome=None, metadata=None,
            reference_type="comment",
        )
        assert v.finding_status == "candidate"
        assert v.confidence == "low"
        assert v.severity == "info"
        assert v.map_reference_type == "inline_data_url"
        assert "inline_data_url_not_decoded" in v.indicators


class RejectedFindingTests(unittest.TestCase):
    def test_404_map_yields_rejected(self) -> None:
        # Spec §Finding status: rejected when checked fallback or
        # referenced map returned a clear non-exposure status.
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=FetchOutcome(
                kind="absent", status=404, body="",
                final_url=f"{_BASE}/a.js.map", content_type="",
            ),
            metadata=None, reference_type="fallback",
        )
        assert v.finding_status == "rejected"
        assert v.confidence == "low"

    def test_cross_origin_resolved_yields_rejected(self) -> None:
        # The resolver said the comment pointed off-host, so we
        # never even fetched the map. Emit a rejected finding so
        # the runner has an audit row.
        v = classify_map_result(
            asset_outcome=_ok_asset(),
            resolved=ResolvedMapUrl(kind="cross_origin", absolute_url=None),
            map_outcome=None, metadata=None,
            reference_type="comment",
        )
        assert v.finding_status == "rejected"
        assert "cross_origin_map_rejected" in v.indicators

    def test_invalid_resolved_yields_rejected(self) -> None:
        v = classify_map_result(
            asset_outcome=_ok_asset(),
            resolved=ResolvedMapUrl(kind="invalid", absolute_url=None),
            map_outcome=None, metadata=None,
            reference_type="comment",
        )
        assert v.finding_status == "rejected"
        assert "invalid_map_reference" in v.indicators


class CandidateFindingTests(unittest.TestCase):
    def test_blocked_map_yields_candidate(self) -> None:
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=FetchOutcome(
                kind="blocked", status=403, body="",
                final_url=f"{_BASE}/a.js.map", content_type="",
            ),
            metadata=None, reference_type="comment",
        )
        assert v.finding_status == "candidate"
        assert v.confidence == "low"
        assert "blocked_map" in v.indicators

    def test_inconclusive_map_yields_candidate(self) -> None:
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=FetchOutcome(
                kind="inconclusive", status=None, body="",
                final_url=f"{_BASE}/a.js.map", content_type="",
            ),
            metadata=None, reference_type="comment",
        )
        assert v.finding_status == "candidate"

    def test_ok_status_but_malformed_yields_candidate(self) -> None:
        # 200 OK but body doesn't parse as Source Map v3 — must NOT
        # be confirmed. Spec §Negative assertions explicitly bans
        # confirming a JSON response that isn't a source map.
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=_ok_map(body="<html>oops</html>"),
            metadata=None,  # validator rejected the body
            reference_type="comment",
        )
        assert v.finding_status == "candidate"
        assert v.confidence == "low"
        assert "malformed_or_not_source_map" in v.indicators


class VerdictShapeTests(unittest.TestCase):
    def test_returns_dataclass_type(self) -> None:
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=_ok_map(), metadata=_metadata(),
            reference_type="comment",
        )
        assert isinstance(v, Verdict)
        assert v.indicators  # non-empty tuple

    def test_indicators_are_tuple_for_persistence(self) -> None:
        v = classify_map_result(
            asset_outcome=_ok_asset(), resolved=_resolved_ok(),
            map_outcome=_ok_map(), metadata=_metadata(),
            reference_type="comment",
        )
        assert isinstance(v.indicators, tuple)
