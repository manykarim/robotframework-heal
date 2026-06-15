"""SessionDriver implementation for AppiumLibrary.

Mobile specifics: the page source covers only the CURRENT screen, so an
off-screen element is *absent*, not "hidden" (`dom_covers_viewport_only`).
`scroll_into_view` is a bounded swipe search ported from the legacy healer.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET

from .protocol import ElementInfo

MAX_SWIPES = 8
_KEEP_ATTRIBUTES = (
    "resource-id", "content-desc", "text", "class", "hint",
    "clickable", "checkable", "scrollable", "bounds",
)
_DISMISS_TEXTS = ("ALLOW", "TURN", "CONFIRM", "OK", "OKAY", "ACCEPT", "CLOSE")


def simplify_appium_xml(source: str) -> str:
    """Strip non-locator attributes from an Appium XML hierarchy."""
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        return source
    for elem in root.iter():
        for attr in list(elem.attrib):
            if attr not in _KEEP_ATTRIBUTES:
                del elem.attrib[attr]
            elif elem.attrib[attr] in ("", "false"):
                del elem.attrib[attr]
    return ET.tostring(root, encoding="unicode")


class AppiumDriver:
    """Wraps an AppiumLibrary instance behind the SessionDriver protocol."""

    library_name = "AppiumLibrary"
    #: page source covers only the rendered screen -> absence may mean off-screen
    dom_covers_viewport_only = True

    def __init__(self, appium_library):
        self._lib = appium_library

    @property
    def _driver(self):
        return self._lib._current_application()

    # ----- locator handling -----

    @staticmethod
    def _strategy(locator: str) -> tuple[str, str]:
        """Map an AppiumLibrary-style locator to a (by, value) pair."""
        if locator.startswith("//") or locator.startswith("(") :
            return "xpath", locator
        for prefix, by in (
            ("xpath=", "xpath"),
            ("accessibility_id=", "accessibility id"),
            ("id=", "id"),
            ("class=", "class name"),
            ("css=", "css selector"),
        ):
            if locator.startswith(prefix):
                return by, locator[len(prefix):]
        return "id", locator

    def _find(self, locator: str) -> list:
        by, value = self._strategy(locator)
        try:
            return self._driver.find_elements(by, value)
        except Exception:
            return []

    # ----- query -----

    def count(self, locator: str) -> int:
        return len(self._find(locator))

    def is_visible(self, locator: str) -> bool:
        elements = self._find(locator)
        if not elements:
            return False
        try:
            return bool(elements[0].is_displayed())
        except Exception:
            return False

    def is_in_viewport(self, locator: str) -> bool | None:
        # present in the current hierarchy == rendered on this screen
        return True if self.count(locator) > 0 else None

    # ----- inspect -----

    def get_page_source(self) -> str:
        try:
            return str(self._driver.page_source)
        except Exception:
            return ""

    def get_simplified_dom(self) -> str:
        return simplify_appium_xml(self.get_page_source())

    def get_element_info(self, locator: str) -> ElementInfo:
        info = ElementInfo(locator=locator)
        elements = self._find(locator)
        if not elements:
            return info
        element = elements[0]
        for attr in _KEEP_ATTRIBUTES:
            try:
                value = element.get_attribute(attr)
            except Exception:
                value = None
            if value:
                info.attributes[attr] = str(value)
        info.tag_name = info.attributes.get("class", "")
        info.inner_text = info.attributes.get("text", "")
        info.visible = self.is_visible(locator)
        info.in_viewport = True
        return info

    def is_page_ready(self) -> bool:
        return True  # no readyState equivalent on mobile

    def open_dialog_locator(self) -> str | None:
        dialog = "//*[contains(@resource-id,'dialog_container')]"
        return dialog if self.count(dialog) >= 1 else None

    def find_dismiss_controls(self) -> list[str]:
        candidates = []
        for text in _DISMISS_TEXTS:
            xpath = f"//*[contains(@text, '{text}')]"
            if self.count(xpath) >= 1:
                candidates.append(xpath)
        return candidates

    def take_screenshot(self) -> bytes | None:
        try:
            return self._driver.get_screenshot_as_png()
        except Exception:
            return None

    # ----- act -----

    def scroll_into_view(self, locator: str) -> bool:
        """Bounded swipe search (down then back up), ported from the legacy healer."""
        if self.count(locator) > 0:
            return True
        driver = self._driver
        try:
            size = driver.get_window_size()
        except Exception:
            return False
        width, height = size["width"], size["height"]

        def swipe_down():
            driver.swipe(width / 2, height * 8 / 9, width / 2, height / 9, 1000)

        def swipe_up():
            driver.swipe(width / 2, height * 2 / 9, width / 2, height * 8 / 9, 1000)

        previous = self.get_page_source()
        for _ in range(MAX_SWIPES):
            swipe_down()
            time.sleep(0.5)
            if self.count(locator) > 0:
                return True
            current = self.get_page_source()
            if current == previous:
                break
            previous = current
        previous = ""
        for _ in range(MAX_SWIPES):
            if self.count(locator) > 0:
                return True
            current = self.get_page_source()
            if current == previous:
                break
            previous = current
            swipe_up()
            time.sleep(0.5)
        return self.count(locator) > 0

    def click(self, locator: str) -> None:
        elements = self._find(locator)
        if not elements:
            raise AssertionError(f"no element for {locator!r}")
        elements[0].click()

    def wait_until_ready(self, timeout_seconds: float) -> bool:
        return True
