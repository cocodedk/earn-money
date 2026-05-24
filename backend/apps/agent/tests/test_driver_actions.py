from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from apps.agent.browser.driver import PlaywrightDriver


def run(coro):
    return asyncio.run(coro)


class TestDriverClick:
    def test_click_known_element(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"link_3": "a >> nth=2"}
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator
        locator.click = AsyncMock()
        driver._page = page

        run(driver.click("link_3"))
        page.locator.assert_called_once_with("a >> nth=2")
        locator.click.assert_awaited_once()

    def test_click_unknown_element_raises(self):
        driver = PlaywrightDriver()
        driver._element_registry = {}
        with pytest.raises(ValueError, match="Unknown element_id"):
            run(driver.click("link_999"))


class TestDriverFill:
    def test_fill_known_element(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"email_field": "input[type='email']"}
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator
        locator.fill = AsyncMock()
        driver._page = page

        run(driver.fill("email_field", "user@example.com"))
        page.locator.assert_called_once_with("input[type='email']")
        locator.fill.assert_awaited_once_with("user@example.com")

    def test_fill_unknown_element_raises(self):
        driver = PlaywrightDriver()
        driver._element_registry = {}
        driver._page = MagicMock()
        with pytest.raises(ValueError, match="Unknown element_id"):
            run(driver.fill("missing_field", "value"))

    def test_fill_empty_value_clears(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"search": "input[name='q']"}
        page = MagicMock()
        locator = MagicMock()
        page.locator.return_value = locator
        locator.fill = AsyncMock()
        driver._page = page

        run(driver.fill("search", ""))
        locator.fill.assert_awaited_once_with("")

    def test_fill_without_page_raises_clear_error(self):
        driver = PlaywrightDriver()
        driver._element_registry = {"email_field": "input[type='email']"}
        driver._page = None
        with pytest.raises(RuntimeError, match="browser not started"):
            run(driver.fill("email_field", "anything"))
