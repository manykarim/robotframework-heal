"""SessionDriver implementation for SeleniumLibrary.

Mechanisms per experiments/selenium-probe/FINDINGS.md. Locator translation:
heal-internal proposals use `css=`/`xpath=`; SeleniumLibrary keywords accept
`css:`/`xpath:` — `to_selenium_locator` converts on the way out (rerun),
while queries resolve through the raw webdriver. Frames: no pierce syntax in
Selenium — frame healing is detect/RCA-only for this driver.
"""

from __future__ import annotations

import time

from bs4 import BeautifulSoup

from .dom import simplify_dom
from .protocol import ElementInfo

_INFO_ATTRIBUTES = ("id", "class", "value", "name", "type", "placeholder", "role")

_SHADOW_SERIALIZER = """
  function ser(node){
    let html="";
    function attrs(n){
      if(!n.attributes || !n.attributes.length) return "";
      return Array.from(n.attributes).map(a=>` ${a.name}="${a.value}"`).join("");
    }
    if(node.nodeType===Node.ELEMENT_NODE){
      html += "<"+node.tagName.toLowerCase()+attrs(node)+">";
      if(node.shadowRoot){ html += ser(node.shadowRoot); }
      else { for(const c of node.childNodes) html += ser(c); }
      html += "</"+node.tagName.toLowerCase()+">";
    } else if(node.nodeType===Node.DOCUMENT_FRAGMENT_NODE){
      for(const c of node.childNodes) html += ser(c);
    } else if(node.nodeType===Node.TEXT_NODE){ html += node.textContent; }
    return html;
  }
  return ser(document.documentElement);
"""


def to_by(locator: str) -> tuple[str, str]:
    """heal/SL locator -> (by, value) for webdriver queries."""
    for prefix in ("css=", "css:"):
        if locator.startswith(prefix):
            return ("css selector", locator[len(prefix):])
    for prefix in ("xpath=", "xpath:"):
        if locator.startswith(prefix):
            return ("xpath", locator[len(prefix):])
    if locator.startswith("//") or locator.startswith("("):
        return ("xpath", locator)
    if locator.startswith("id=") or locator.startswith("id:"):
        return ("id", locator[3:])
    return ("css selector", locator)


def to_selenium_locator(locator: str) -> str:
    """heal-internal proposal -> SeleniumLibrary keyword syntax."""
    if locator.startswith("css="):
        return "css:" + locator[4:]
    if locator.startswith("xpath="):
        return "xpath:" + locator[6:]
    return locator


class SeleniumDriver:
    """Wraps a SeleniumLibrary instance behind the SessionDriver protocol."""

    library_name = "SeleniumLibrary"

    def __init__(self, selenium_library):
        self._lib = selenium_library

    @property
    def _driver(self):
        return self._lib.driver

    def _find(self, locator: str) -> list:
        by, value = to_by(locator)
        try:
            return self._driver.find_elements(by, value)
        except Exception:
            return []

    # ----- query -----

    def count(self, locator: str) -> int:
        return len(self._find(locator))

    def is_visible(self, locator: str) -> bool:
        elements = self._find(locator)
        try:
            return bool(elements and elements[0].is_displayed())
        except Exception:
            return False

    def is_in_viewport(self, locator: str) -> bool | None:
        elements = self._find(locator)
        if not elements:
            return None
        try:
            return bool(
                self._driver.execute_script(
                    "const r=arguments[0].getBoundingClientRect();"
                    "return r.bottom>0 && r.right>0 && r.top<window.innerHeight && r.left<window.innerWidth",
                    elements[0],
                )
            )
        except Exception:
            return None

    # ----- inspect -----

    def get_page_source(self) -> str:
        try:
            return str(self._driver.execute_script(_SHADOW_SERIALIZER))
        except Exception:
            pass
        try:
            return str(self._driver.page_source)
        except Exception:
            return ""

    def get_simplified_dom(self) -> str:
        dom = simplify_dom(self.get_page_source())
        # Selenium has no frame-piercing selector syntax: content inside
        # iframes is unreachable for healing (design D5) — say so in the
        # evidence so proposals and RCA reflect the limitation.
        try:
            frame_count = len(BeautifulSoup(dom, "html.parser").find_all(["iframe", "frame"]))
        except Exception:
            frame_count = 0
        if frame_count:
            dom += (
                f"\n<!-- NOTE: page contains {frame_count} iframe(s)/frame(s); SeleniumLibrary "
                "healing CANNOT reach elements inside frames — if the intended element lives "
                "in a frame, this failure is not healable and needs the test to switch frames -->"
            )
        return dom

    def get_element_info(self, locator: str) -> ElementInfo:
        info = ElementInfo(locator=locator)
        elements = self._find(locator)
        if not elements:
            return info
        element = elements[0]
        try:
            info.tag_name = str(element.tag_name or "").upper()
        except Exception:
            pass
        for attr in _INFO_ATTRIBUTES:
            try:
                value = element.get_attribute(attr)
            except Exception:
                value = None
            if value:
                info.attributes[attr] = str(value)
        try:
            info.inner_text = str(self._driver.execute_script("return arguments[0].innerText", element) or "")
        except Exception:
            pass
        info.visible = self.is_visible(locator)
        info.in_viewport = self.is_in_viewport(locator)
        return info

    def is_page_ready(self) -> bool:
        try:
            return self._driver.execute_script("return document.readyState") == "complete"
        except Exception:
            return True

    def open_dialog_locator(self) -> str | None:
        try:
            soup = BeautifulSoup(self._driver.page_source, "html.parser")
        except Exception:
            return None
        if soup.find("dialog", {"open": True}) is not None:
            return "css=dialog[open]"
        return None

    _DISMISS_TEXTS = ("close", "ok", "okay", "accept", "dismiss", "got it", "agree", "×", "x")

    def find_dismiss_controls(self) -> list[str]:
        try:
            soup = BeautifulSoup(self._driver.page_source, "html.parser")
        except Exception:
            return []
        dialog = soup.find("dialog", {"open": True})
        if dialog is None:
            return []
        candidates: list[str] = []
        controls = dialog.find_all(["button", "a", "input"])
        for index, control in enumerate(controls):
            text = (control.get_text() or control.get("value") or "").strip().lower()
            if any(marker in text for marker in self._DISMISS_TEXTS):
                candidates.append(f"xpath=(//dialog[@open]//{control.name})[{index + 1}]")
        if not candidates and len(controls) == 1:
            candidates.append(f"css=dialog[open] {controls[0].name}")
        return [c for c in candidates if self.count(c) == 1]

    def find_form_issues(self) -> list[str]:
        issues: list[str] = []
        try:
            soup = BeautifulSoup(self._driver.page_source, "html.parser")
        except Exception:
            return issues
        for field in soup.find_all(["input", "textarea", "select"]):
            name = field.get("id") or field.get("name") or field.get("placeholder") or field.name
            required = field.has_attr("required") or field.get("aria-required") == "true"
            if required and not (field.get("value") or "").strip() and field.name != "select":
                issues.append(f"required field '{name}' is empty")
            if field.get("aria-invalid") == "true":
                issues.append(f"field '{name}' is marked invalid")
        for alert in soup.find_all(attrs={"role": "alert"}):
            text = alert.get_text(strip=True)
            if text:
                issues.append(f"validation message: '{text[:120]}'")
        return issues

    def take_screenshot(self) -> bytes | None:
        try:
            return self._driver.get_screenshot_as_png()
        except Exception:
            return None

    # ----- act -----

    def scroll_into_view(self, locator: str) -> bool:
        elements = self._find(locator)
        if not elements:
            return False
        try:
            self._driver.execute_script("arguments[0].scrollIntoView({block:'center'})", elements[0])
        except Exception:
            return False
        return self.is_visible(locator)

    def fill_text(self, locator: str, value: str) -> None:
        elements = self._find(locator)
        if not elements:
            raise AssertionError(f"no element for {locator!r}")
        elements[0].clear()
        elements[0].send_keys(value)

    def click(self, locator: str) -> None:
        elements = self._find(locator)
        if not elements:
            raise AssertionError(f"no element for {locator!r}")
        elements[0].click()

    def wait_until_ready(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self.is_page_ready():
                return True
            time.sleep(0.5)
        return self.is_page_ready()
