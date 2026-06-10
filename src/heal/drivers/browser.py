"""SessionDriver implementation for robotframework-browser (Playwright)."""

from __future__ import annotations

import time

from bs4 import BeautifulSoup

from .dom import simplify_dom
from .protocol import ElementInfo

_SHADOW_DOM_EXISTS_SCRIPT = """() => {
  return Array.from(document.querySelectorAll('*')).some(el => el.shadowRoot);
}"""

# Serializes the full DOM including shadow roots (ported from browser_healing).
_FULL_HTML_SCRIPT = """() => {
  function getAttributes(node) {
    if (node.attributes && node.attributes.length > 0) {
      return Array.from(node.attributes).map(attr => ` ${attr.name}="${attr.value}"`).join("");
    }
    return "";
  }
  function processNode(node) {
    let html = "";
    if (node.nodeType === Node.ELEMENT_NODE) {
      html += `<${node.tagName.toLowerCase()}${getAttributes(node)}>`;
      if (node.shadowRoot) {
        html += processNode(node.shadowRoot);
      } else {
        for (let child of node.childNodes) { html += processNode(child); }
      }
      html += `</${node.tagName.toLowerCase()}>`;
    } else if (node.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
      for (let child of node.childNodes) { html += processNode(child); }
    } else if (node.nodeType === Node.TEXT_NODE) {
      html += node.textContent;
    }
    return html;
  }
  return processNode(document.documentElement);
}"""

_READY_STATE_SCRIPT = """() => { return document.readyState == 'complete'; }"""

_IN_VIEWPORT_SCRIPT = """(elem) => {
  const rect = elem.getBoundingClientRect();
  return (
    rect.bottom > 0 && rect.right > 0 &&
    rect.top < (window.innerHeight || document.documentElement.clientHeight) &&
    rect.left < (window.innerWidth || document.documentElement.clientWidth)
  );
}"""

_INFO_ATTRIBUTES = ("id", "class", "value", "name", "type", "placeholder", "role")


class BrowserDriver:
    """Wraps a Browser library instance behind the SessionDriver protocol.

    All methods swallow driver-level errors into neutral values (0 / False /
    None) — the engine treats missing evidence as "not collected", never as a
    crash. Must be called on the RF main thread.
    """

    library_name = "Browser"

    def __init__(self, browser):
        self._browser = browser

    # ----- query -----

    def count(self, locator: str) -> int:
        try:
            return int(self._browser.get_element_count(locator))
        except Exception:
            return 0

    def is_visible(self, locator: str) -> bool:
        try:
            return "visible" in self._browser.get_element_states(locator)
        except Exception:
            return False

    def is_in_viewport(self, locator: str) -> bool | None:
        try:
            return bool(self._browser.evaluate_javascript(locator, _IN_VIEWPORT_SCRIPT))
        except Exception:
            return None

    # ----- inspect -----

    def get_page_source(self) -> str:
        try:
            if bool(self._browser.evaluate_javascript(None, _SHADOW_DOM_EXISTS_SCRIPT)):
                return str(self._browser.evaluate_javascript(None, _FULL_HTML_SCRIPT))
        except Exception:
            pass
        try:
            return str(self._browser.get_page_source())
        except Exception:
            return ""

    def get_simplified_dom(self) -> str:
        return simplify_dom(self.get_page_source())

    def get_element_info(self, locator: str) -> ElementInfo:
        info = ElementInfo(locator=locator)
        try:
            info.tag_name = str(self._browser.evaluate_javascript(locator, "(elem) => elem.tagName") or "")
        except Exception:
            pass
        for attr in _INFO_ATTRIBUTES:
            try:
                value = self._browser.get_attribute(locator, attr)
            except Exception:
                value = None
            if value:
                info.attributes[attr] = str(value)
        try:
            info.inner_text = str(self._browser.evaluate_javascript(locator, "(elem) => elem.innerText") or "")
        except Exception:
            pass
        info.visible = self.is_visible(locator)
        info.in_viewport = self.is_in_viewport(locator)
        return info

    def is_page_ready(self) -> bool:
        try:
            return bool(self._browser.evaluate_javascript(None, _READY_STATE_SCRIPT))
        except Exception:
            return True  # cannot tell -> do not classify as loading

    def open_dialog_locator(self) -> str | None:
        try:
            soup = BeautifulSoup(self._browser.get_page_source(), "html.parser")
        except Exception:
            return None
        if soup.find("dialog", {"open": True}) is not None:
            return "dialog[open]"
        return None

    def take_screenshot(self) -> bytes | None:
        try:
            import base64

            data = self._browser.take_screenshot(
                fullPage=False, log_screenshot=False, return_as=_screenshot_base64_type()
            )
            return base64.b64decode(data)
        except Exception:
            return None

    # ----- act -----

    def scroll_into_view(self, locator: str) -> bool:
        try:
            self._browser.scroll_to_element(locator)
        except Exception:
            try:
                self._browser.evaluate_javascript(locator, "(elem) => elem.scrollIntoView({block: 'center'})")
            except Exception:
                return False
        return self.is_visible(locator)

    def click(self, locator: str) -> None:
        self._browser.click(locator)

    def wait_until_ready(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.is_page_ready():
                return True
            time.sleep(0.5)
        return self.is_page_ready()


def _screenshot_base64_type():
    from Browser.utils.data_types import ScreenshotReturnType

    return ScreenshotReturnType.base64
