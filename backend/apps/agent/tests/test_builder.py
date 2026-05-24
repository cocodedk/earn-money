from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.agent.observations.builder import ObservationBuilder
from apps.agent.observations.page import PageObservation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


def _mock_page(
    url: str = "https://example.com/",
    title: str = "Home",
    snapshot: dict | None = None,
    cookies: list[dict] | None = None,
) -> MagicMock:
    page = MagicMock()
    page.url = url
    page.title = AsyncMock(return_value=title)
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(return_value=snapshot or {})
    page.context = MagicMock()
    page.context.cookies = AsyncMock(return_value=cookies or [])
    return page


def _builder() -> ObservationBuilder:
    return ObservationBuilder("https://example.com")


# ---------------------------------------------------------------------------
# ID counter tests
# ---------------------------------------------------------------------------

class TestNextId:
    def test_sequential_same_prefix(self):
        b = _builder()
        assert b._next_id("link") == "link_0"
        assert b._next_id("link") == "link_1"

    def test_independent_prefixes(self):
        b = _builder()
        assert b._next_id("link") == "link_0"
        assert b._next_id("btn") == "btn_0"
        assert b._next_id("link") == "link_1"


# ---------------------------------------------------------------------------
# URL ref tests
# ---------------------------------------------------------------------------

class TestUrlRef:
    def test_caches_same_path(self):
        b = _builder()
        r1 = b._url_ref("/about")
        r2 = b._url_ref("/about")
        assert r1 == r2

    def test_different_paths_get_different_refs(self):
        b = _builder()
        r1 = b._url_ref("/a")
        r2 = b._url_ref("/b")
        assert r1 != r2

    def test_resolve_url_ref_roundtrip(self):
        b = _builder()
        ref = b._url_ref("/login")
        assert b.resolve_url_ref(ref) == "/login"

    def test_resolve_unknown_ref_returns_none(self):
        b = _builder()
        assert b.resolve_url_ref("url_999") is None


# ---------------------------------------------------------------------------
# build_page_observation — happy path
# ---------------------------------------------------------------------------

class TestBuildPageObservation:
    def test_returns_page_observation(self):
        page = _mock_page()
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert isinstance(obs, PageObservation)

    def test_identity_url_and_title(self):
        page = _mock_page(url="https://example.com/login", title="Login")
        obs = run(_builder().build_page_observation(page, 1, "enumerate", "act_1", []))
        assert obs.identity.url == "https://example.com/login"
        assert obs.identity.title == "Login"

    def test_meta_turn_and_phase(self):
        page = _mock_page()
        obs = run(_builder().build_page_observation(page, 3, "probe", "act_3", []))
        assert obs.meta.turn_index == 3
        assert obs.meta.phase == "probe"

    def test_elapsed_ms_non_negative(self):
        page = _mock_page()
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert obs.meta.elapsed_ms >= 0

    def test_empty_snapshot_yields_no_elements(self):
        page = _mock_page(snapshot={})
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert obs.elements.links == []
        assert obs.elements.buttons == []

    def test_link_parsed_from_snapshot(self):
        snapshot = {"children": [
            {"role": "link", "name": "About", "url": "/about"},
        ]}
        page = _mock_page(snapshot=snapshot)
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert len(obs.elements.links) == 1
        link = obs.elements.links[0]
        assert link.text == "About"
        assert link.href == "/about"
        assert link.element_id == "link_0"

    def test_button_parsed_from_snapshot(self):
        snapshot = {"children": [
            {"role": "button", "name": "Submit"},
        ]}
        page = _mock_page(snapshot=snapshot)
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert len(obs.elements.buttons) == 1
        assert obs.elements.buttons[0].element_id == "btn_0"
        assert obs.elements.buttons[0].text == "Submit"

    def test_input_parsed_from_snapshot(self):
        snapshot = {"children": [
            {"role": "textbox", "name": "Email"},
        ]}
        page = _mock_page(snapshot=snapshot)
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert len(obs.elements.inputs) == 1
        assert obs.elements.inputs[0].element_id == "input_0"

    def test_controller_assigned_ids_are_sequential(self):
        snapshot = {"children": [
            {"role": "link", "name": "Home", "url": "/"},
            {"role": "link", "name": "Login", "url": "/login"},
            {"role": "button", "name": "Go"},
        ]}
        page = _mock_page(snapshot=snapshot)
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        ids = [l.element_id for l in obs.elements.links]
        assert ids == ["link_0", "link_1"]
        assert obs.elements.buttons[0].element_id == "btn_0"


# ---------------------------------------------------------------------------
# Cookie redaction
# ---------------------------------------------------------------------------

class TestCookieRedaction:
    def test_cookie_values_are_stripped(self):
        raw = [{"name": "session", "value": "secret123", "domain": "example.com",
                "secure": True, "httpOnly": True}]
        page = _mock_page(cookies=raw)
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert len(obs.cookies) == 1
        cookie = obs.cookies[0]
        assert cookie.name == "session"
        assert cookie.domain == "example.com"
        assert cookie.secure is True
        assert cookie.http_only is True
        # PageObservation.cookies are CookieInfo — no value field
        assert not hasattr(cookie, "value")

    def test_no_cookies_empty_list(self):
        page = _mock_page(cookies=[])
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert obs.cookies == []


# ---------------------------------------------------------------------------
# Route extraction
# ---------------------------------------------------------------------------

class TestRouteExtraction:
    def test_relative_link_becomes_route(self):
        snapshot = {"children": [{"role": "link", "name": "X", "url": "/shop"}]}
        page = _mock_page(snapshot=snapshot)
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert any(r.path == "/shop" for r in obs.discovered.routes)

    def test_absolute_same_origin_link_becomes_route(self):
        snapshot = {"children": [
            {"role": "link", "name": "X", "url": "https://example.com/cart"}
        ]}
        page = _mock_page(snapshot=snapshot)
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert any(r.path == "/cart" for r in obs.discovered.routes)

    def test_external_link_excluded(self):
        snapshot = {"children": [
            {"role": "link", "name": "X", "url": "https://evil.com/attack"}
        ]}
        page = _mock_page(snapshot=snapshot)
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", []))
        assert obs.discovered.routes == []


# ---------------------------------------------------------------------------
# Asset extraction from network log
# ---------------------------------------------------------------------------

class TestAssetExtraction:
    def test_js_asset_detected(self):
        entries = [{"url": "https://example.com/app.js", "method": "GET",
                    "status": 200, "content_type": "application/javascript"}]
        page = _mock_page()
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", entries))
        assert len(obs.discovered.assets) == 1
        assert obs.discovered.assets[0].asset_type == "script"

    def test_non_asset_url_excluded(self):
        entries = [{"url": "https://example.com/api/data", "method": "GET",
                    "status": 200, "content_type": "application/json"}]
        page = _mock_page()
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", entries))
        assert obs.discovered.assets == []

    def test_asset_ref_id_assigned(self):
        entries = [{"url": "https://example.com/style.css", "method": "GET",
                    "status": 200, "content_type": "text/css"}]
        page = _mock_page()
        obs = run(_builder().build_page_observation(page, 0, "recon", "act_0", entries))
        assert obs.discovered.assets[0].asset_ref == "asset_0"


# ---------------------------------------------------------------------------
# Form extraction from a11y snapshot
# ---------------------------------------------------------------------------

class TestFormExtraction:
    def test_form_node_creates_form_element(self):
        """role=form node produces FormElement; child inputs land in forms[0].fields
        and also in elements.inputs; child button lands in elements.buttons."""
        builder = ObservationBuilder("https://example.com")
        children = [
            {
                "role": "form",
                "name": "Login",
                "children": [
                    {"role": "textbox", "name": "Email"},
                    {"role": "textbox", "name": "Password"},
                    {"role": "button", "name": "Sign In", "type": "submit"},
                ],
            },
        ]
        elements, visible = builder._parse_a11y(children)
        assert len(elements.forms) == 1
        assert elements.forms[0].element_id.startswith("form_")
        assert len(elements.forms[0].fields) == 2
        assert len(elements.inputs) == 2
        assert len(elements.buttons) == 1

    def test_orphan_inputs_remain_standalone(self):
        """Inputs not under a form node are still in elements.inputs."""
        builder = ObservationBuilder("https://example.com")
        children = [
            {"role": "textbox", "name": "Search"},
            {"role": "button", "name": "Go"},
        ]
        elements, visible = builder._parse_a11y(children)
        assert len(elements.forms) == 0
        assert len(elements.inputs) == 1
        assert len(elements.buttons) == 1

    def test_form_fields_have_correct_types(self):
        """FormField.type reflects the a11y role of each child input."""
        builder = ObservationBuilder("https://example.com")
        children = [
            {
                "role": "form",
                "name": "Register",
                "children": [
                    {"role": "textbox", "name": "Username"},
                    {"role": "combobox", "name": "Country"},
                    {"role": "searchbox", "name": "Filter"},
                ],
            },
        ]
        elements, visible = builder._parse_a11y(children)
        form = elements.forms[0]
        assert form.fields[0].type == "textbox"
        assert form.fields[1].type == "combobox"
        assert form.fields[2].type == "searchbox"

    def test_nested_form_controls_are_grouped(self):
        """Inputs inside a role=group child of role=form are also grouped."""
        builder = ObservationBuilder("https://example.com")
        children = [
            {
                "role": "form",
                "name": "Login",
                "children": [
                    {
                        "role": "group",
                        "name": "Credentials",
                        "children": [
                            {"role": "textbox", "name": "Email"},
                            {"role": "textbox", "name": "Password"},
                            {"role": "button", "name": "Sign In", "type": "submit"},
                        ],
                    },
                ],
            },
        ]
        elements, visible = builder._parse_a11y(children)
        assert len(elements.forms) == 1
        assert [f.name for f in elements.forms[0].fields] == ["Email", "Password"]
        assert len(elements.inputs) == 2
        assert len(elements.buttons) == 1
