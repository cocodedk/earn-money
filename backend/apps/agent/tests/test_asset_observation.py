from __future__ import annotations

import pytest
from apps.agent.observations.assets import AssetExcerpt, AssetObservation

_UNTRUSTED = "untrusted_target_content"


def _minimal(**kwargs) -> AssetObservation:
    return AssetObservation(
        asset_ref="asset-1",
        path="/static/app.js",
        type="script",
        size_bytes=1024,
        truncated=False,
        **kwargs,
    )


class TestAssetExcerpt:
    def test_fields(self):
        ex = AssetExcerpt(
            context="function login()",
            match="password",
            surrounding="if(password==null)",
        )
        assert ex.match == "password"
        assert ex.context == "function login()"
        assert ex.surrounding == "if(password==null)"


class TestAssetObservation:
    def test_defaults(self):
        obs = _minimal()
        assert obs.excerpts == []
        assert obs.strings_of_interest == []

    def test_to_dict_adds_trust(self):
        obs = _minimal()
        d = obs.to_dict()
        assert d["trust"] == _UNTRUSTED

    def test_to_dict_fields(self):
        obs = _minimal()
        d = obs.to_dict()
        assert d["asset_ref"] == "asset-1"
        assert d["path"] == "/static/app.js"
        assert d["type"] == "script"
        assert d["size_bytes"] == 1024
        assert d["truncated"] is False

    def test_to_dict_with_excerpts(self):
        ex = AssetExcerpt(context="ctx", match="admin", surrounding="surr")
        obs = _minimal(excerpts=[ex])
        d = obs.to_dict()
        assert d["excerpts"][0]["match"] == "admin"

    def test_to_dict_with_strings_of_interest(self):
        obs = _minimal(strings_of_interest=["apiKey", "token"])
        d = obs.to_dict()
        assert "apiKey" in d["strings_of_interest"]

    def test_truncated_true(self):
        obs = AssetObservation(
            asset_ref="asset-2",
            path="/big.js",
            type="script",
            size_bytes=200_000,
            truncated=True,
        )
        d = obs.to_dict()
        assert d["truncated"] is True
        assert d["size_bytes"] == 200_000

    def test_trust_not_overridable_in_dataclass(self):
        # AssetObservation has no 'trust' field; to_dict() injects it.
        obs = _minimal()
        assert not hasattr(obs, "trust")
        d = obs.to_dict()
        assert d["trust"] == _UNTRUSTED
