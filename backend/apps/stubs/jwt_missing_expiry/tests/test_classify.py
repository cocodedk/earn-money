"""Tests for stub 3.11 JWT missing-expiry classifier."""
from __future__ import annotations

import pytest

from apps.stubs.jwt_missing_expiry.classify import (
    ExpiryResult,
    ExpiryStatus,
    classify_jwt_expiry,
)
from apps.stubs._shared.auth.jwt_utils import ParsedJwt


def _jwt(payload: dict, header: dict | None = None) -> ParsedJwt:
    return ParsedJwt(
        header=header or {"alg": "HS256", "typ": "JWT"},
        payload=payload,
        signature_present=True,
    )


class TestClassifyMissingExp:
    def test_access_token_missing_exp_confirmed_high(self):
        result = classify_jwt_expiry(_jwt({"sub": "u1"}), token_kind="access_token")
        assert result.status == ExpiryStatus.CONFIRMED
        assert result.confidence == "high"
        assert result.exp is None

    def test_id_token_missing_exp_confirmed_high(self):
        result = classify_jwt_expiry(_jwt({"sub": "u1"}), token_kind="id_token")
        assert result.status == ExpiryStatus.CONFIRMED
        assert result.confidence == "high"

    def test_session_jwt_missing_exp_confirmed_high(self):
        result = classify_jwt_expiry(_jwt({}), token_kind="session_jwt")
        assert result.status == ExpiryStatus.CONFIRMED
        assert result.confidence == "high"

    def test_refresh_missing_exp_no_policy_candidate_medium(self):
        result = classify_jwt_expiry(_jwt({}), token_kind="refresh_token")
        assert result.status == ExpiryStatus.CANDIDATE
        assert result.confidence == "medium"

    def test_refresh_missing_exp_policy_requires_expiry_confirmed(self):
        result = classify_jwt_expiry(
            _jwt({}), token_kind="refresh_token", refresh_expiry_required=True
        )
        assert result.status == ExpiryStatus.CONFIRMED
        assert result.confidence == "high"

    def test_unknown_jwt_missing_exp_candidate_low(self):
        result = classify_jwt_expiry(_jwt({}), token_kind="unknown_jwt")
        assert result.status == ExpiryStatus.CANDIDATE
        assert result.confidence == "low"

    def test_token_with_valid_exp_rejected_high(self):
        result = classify_jwt_expiry(
            _jwt({"exp": 9999999999}), token_kind="access_token"
        )
        assert result.status == ExpiryStatus.REJECTED
        assert result.confidence == "high"
        assert result.exp == 9999999999

    def test_malformed_non_numeric_exp_confirmed_medium(self):
        result = classify_jwt_expiry(
            _jwt({"exp": "never"}), token_kind="access_token"
        )
        assert result.status == ExpiryStatus.CONFIRMED
        assert result.confidence == "medium"

    def test_exp_zero_treated_as_missing_confirmed(self):
        result = classify_jwt_expiry(
            _jwt({"exp": 0}), token_kind="access_token"
        )
        assert result.status == ExpiryStatus.CONFIRMED
        assert result.confidence == "high"

    def test_returns_expiry_result_type(self):
        result = classify_jwt_expiry(_jwt({}), token_kind="access_token")
        assert isinstance(result, ExpiryResult)
