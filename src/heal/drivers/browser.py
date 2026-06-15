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

# Frame-evidence defaults settled experimentally (experiments/dom-edge-cases):
# visible frames >= 20x20px, depth <= 2, top 5 by area, bounded per-frame share.
FRAME_MIN_SIZE = 20
FRAME_MAX_COUNT = 5
FRAME_MAX_DEPTH = 2
FRAME_CHARS_SHARE = 4  # per-frame cap = MAX_DOM_CHARS / share


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
        """Curated main DOM plus tagged sections for interactable frames.

        Each frame section states its pierce prefix so the locator agent can
        propose `frame >>> inner` selectors (verified unchanged by count()).
        """
        from ..core.evidence import MAX_DOM_CHARS

        parts = [simplify_dom(self.get_page_source())]
        per_frame_cap = MAX_DOM_CHARS // FRAME_CHARS_SHARE
        for chain, html in self.frame_sections():
            parts.append(
                f'\n<!-- FRAME {chain} : selectors for elements inside this section '
                f'MUST be prefixed with "{chain} >>> " -->\n'
                + simplify_dom(html)[:per_frame_cap]
            )
        return "".join(parts)

    def frame_sections(self) -> list[tuple[str, str]]:
        """(pierce-chain, raw frame HTML) for interactable frames, depth-limited."""
        try:
            main = self._browser.get_page_source()
        except Exception:
            return []
        sections: list[tuple[str, str, float]] = []
        self._collect_frames(main, prefix="", depth=1, sections=sections)
        sections.sort(key=lambda s: -s[2])  # largest frames first
        return [(chain, html) for chain, html, _ in sections[:FRAME_MAX_COUNT]]

    def _collect_frames(self, source_html: str, prefix: str, depth: int, sections: list) -> None:
        if depth > FRAME_MAX_DEPTH:
            return
        soup = BeautifulSoup(source_html, "html.parser")
        for frame in soup.find_all(["iframe", "frame"]):
            selector = self._frame_selector(frame)
            if selector is None:
                continue
            chain = f"{prefix} >>> {selector}" if prefix else selector
            area = self._frame_area(chain)
            if area is None:  # hidden or too small -> non-interactable content
                continue
            try:
                html = str(self._browser.evaluate_javascript(f"{chain} >>> css=html", "(el) => el.outerHTML"))
            except Exception:
                continue  # unserializable frame: skip, main DOM still notes the element
            sections.append((chain, html, area))
            self._collect_frames(html, prefix=chain, depth=depth + 1, sections=sections)

    @staticmethod
    def _frame_selector(frame) -> str | None:
        if frame.get("id"):
            return f"id={frame['id']}"
        if frame.get("name"):
            return f'css={frame.name}[name="{frame["name"]}"]'
        return None  # unaddressable without a stable handle

    def _frame_area(self, chain: str) -> float | None:
        try:
            if "visible" not in self._browser.get_element_states(chain):
                return None
            bbox = self._browser.get_boundingbox(chain)
            width, height = float(bbox["width"]), float(bbox["height"])
        except Exception:
            return None
        if width < FRAME_MIN_SIZE or height < FRAME_MIN_SIZE:
            return None
        return width * height

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

    _DISMISS_TEXTS = ("close", "ok", "okay", "accept", "dismiss", "got it", "agree", "×", "x")

    def find_dismiss_controls(self) -> list[str]:
        """Deterministic dismiss candidates inside the open dialog, best first."""
        try:
            soup = BeautifulSoup(self._browser.get_page_source(), "html.parser")
        except Exception:
            return []
        dialog = soup.find("dialog", {"open": True})
        if dialog is None:
            return []
        candidates: list[str] = []
        controls = dialog.find_all(["button", "a", "input"])
        for control in controls:
            text = (control.get_text() or control.get("value") or "").strip().lower()
            if any(marker in text for marker in self._DISMISS_TEXTS):
                selector = f'dialog[open] {control.name}:has-text("{text[:30]}")'
                candidates.append(selector)
        # fall back to any single button in the dialog
        if not candidates and len(controls) == 1:
            candidates.append(f"dialog[open] {controls[0].name}")
        return [c for c in candidates if self.count(c) == 1]

    def take_screenshot(self) -> bytes | None:
        try:
            import base64

            data = self._browser.take_screenshot(
                fullPage=False, log_screenshot=False, return_as=_screenshot_base64_type()
            )
            return base64.b64decode(data)
        except Exception:
            return None

    def disambiguate(self, locator: str) -> str | None:
        """Refine a multi-match locator to a single element (legacy-parity trick).

        Prefers the only visible match; falls back to the first visible match.
        Returns None when no refinement reaches a usable element.
        """
        visible = f"{locator}:visible"
        try:
            count = self.count(visible)
            if count == 1:
                return visible
            if count > 1:
                return f"{visible} >> nth=0"
        except Exception:
            pass
        return None

    def find_form_issues(self) -> list[str]:
        """Required-but-empty and aria-invalid fields plus visible error texts."""
        issues: list[str] = []
        try:
            soup = BeautifulSoup(self._browser.get_page_source(), "html.parser")
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

    # ----- act -----

    def fill_text(self, locator: str, value: str) -> None:
        self._browser.fill_text(locator, value)

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
