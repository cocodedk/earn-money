from __future__ import annotations

import pytest
from apps.agent.observations.page import (
    PageIdentity,
    PageObservation,
    ObservationMeta,
    Elements,
    VisibleTextBlock,
    DiscoveredItems,
    DiscoveredRoute,
    DiscoveredAsset,
    HtmlExcerpt,
    NetworkEntry,
    CookieInfo,
    StorageKey,
    ConsoleMessage,
    ScreenshotRef,
    LinkElement,
    ButtonElement,
    FormElement,
    FormField,
    InputElement,
)

_UNTRUSTED = "untrusted_target_content"


def _minimal_obs(**kwargs) -> PageObservation:
    return PageObservation(
        identity=PageIdentity(url="https://example.com/", title="Home", status_code=200),
        meta=ObservationMeta(turn_index=0, phase="recon", elapsed_ms=42),
        **kwargs,
    )


class TestPageIdentity:
    def test_fields(self):
        pi = PageIdentity(url="https://x.com/", title="X", status_code=200)
        assert pi.url == "https://x.com/"
        assert pi.status_code == 200


class TestElements:
    def test_defaults_empty(self):
        e = Elements()
        assert e.links == []
        assert e.buttons == []
        assert e.forms == []
        assert e.inputs == []

    def test_with_link(self):
        link = LinkElement(element_id="l1", href="/about", text="About")
        e = Elements(links=[link])
        assert e.links[0].href == "/about"

    def test_with_button(self):
        btn = ButtonElement(element_id="b1", text="Submit")
        assert btn.type == "button"

    def test_form_with_fields(self):
        ff = FormField(name="username", type="text", required=True)
        form = FormElement(element_id="f1", action="/login", method="POST", fields=[ff])
        assert form.fields[0].required is True

    def test_input_element(self):
        inp = InputElement(element_id="i1", name="q", type="text", placeholder="Search")
        assert inp.placeholder == "Search"


class TestVisibleTextBlock:
    def test_trust_annotation(self):
        vt = VisibleTextBlock(text="Hello world")
        assert vt.trust == _UNTRUSTED

    def test_explicit_selector(self):
        vt = VisibleTextBlock(text="Nav text", selector="nav")
        assert vt.selector == "nav"


class TestDiscoveredItems:
    def test_trust_annotation(self):
        di = DiscoveredItems()
        assert di.trust == _UNTRUSTED

    def test_with_route(self):
        di = DiscoveredItems(routes=[DiscoveredRoute(path="/api/users")])
        assert di.routes[0].path == "/api/users"
        assert di.routes[0].method == "GET"

    def test_with_asset(self):
        da = DiscoveredAsset(asset_ref="a1", url="/static/app.js", asset_type="script")
        di = DiscoveredItems(assets=[da])
        assert di.assets[0].asset_type == "script"


class TestHtmlExcerpt:
    def test_trust_annotation(self):
        he = HtmlExcerpt(selector="#main", html="<div>x</div>")
        assert he.trust == _UNTRUSTED


class TestConsoleMessage:
    def test_trust_annotation(self):
        cm = ConsoleMessage(level="error", text="undefined is not a function")
        assert cm.trust == _UNTRUSTED


class TestPageObservation:
    def test_default_trust(self):
        obs = _minimal_obs()
        assert obs.trust == _UNTRUSTED

    def test_to_dict_returns_dict(self):
        obs = _minimal_obs()
        d = obs.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_identity(self):
        obs = _minimal_obs()
        d = obs.to_dict()
        assert d["identity"]["url"] == "https://example.com/"
        assert d["identity"]["status_code"] == 200

    def test_to_dict_meta(self):
        obs = _minimal_obs()
        d = obs.to_dict()
        assert d["meta"]["phase"] == "recon"
        assert d["meta"]["turn_index"] == 0

    def test_to_dict_trust(self):
        obs = _minimal_obs()
        d = obs.to_dict()
        assert d["trust"] == _UNTRUSTED

    def test_to_dict_visible_text_trust(self):
        obs = _minimal_obs(
            visible_text=[VisibleTextBlock(text="some content", selector="p")]
        )
        d = obs.to_dict()
        assert d["visible_text"][0]["trust"] == _UNTRUSTED

    def test_to_dict_console_trust(self):
        obs = _minimal_obs(
            console=[ConsoleMessage(level="warn", text="warn msg")]
        )
        d = obs.to_dict()
        assert d["console"][0]["trust"] == _UNTRUSTED

    def test_to_dict_html_excerpts_trust(self):
        obs = _minimal_obs(
            html_excerpts=[HtmlExcerpt(selector="body", html="<body/>")]
        )
        d = obs.to_dict()
        assert d["html_excerpts"][0]["trust"] == _UNTRUSTED

    def test_to_dict_discovered_trust(self):
        obs = _minimal_obs()
        d = obs.to_dict()
        assert d["discovered"]["trust"] == _UNTRUSTED

    def test_screenshot_none_by_default(self):
        obs = _minimal_obs()
        assert obs.screenshot is None
        d = obs.to_dict()
        assert d["screenshot"] is None

    def test_screenshot_ref(self):
        obs = _minimal_obs(
            screenshot=ScreenshotRef(ref="shot-1", width=1280, height=800)
        )
        d = obs.to_dict()
        assert d["screenshot"]["ref"] == "shot-1"

    def test_network_entries(self):
        obs = _minimal_obs(
            network=[NetworkEntry(url="/api/v1", method="GET", status=200)]
        )
        d = obs.to_dict()
        assert d["network"][0]["status"] == 200

    def test_cookies(self):
        obs = _minimal_obs(
            cookies=[CookieInfo(name="session", domain="example.com", secure=True)]
        )
        d = obs.to_dict()
        assert d["cookies"][0]["secure"] is True

    def test_storage_keys(self):
        obs = _minimal_obs(
            storage_keys=[StorageKey(key="token", storage_type="localStorage")]
        )
        d = obs.to_dict()
        assert d["storage_keys"][0]["storage_type"] == "localStorage"
