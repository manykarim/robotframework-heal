"""BrowserDriver logic tests with a duck-typed fake Browser library."""

from heal.drivers.browser import BrowserDriver
from heal.drivers.protocol import SessionDriver

PAGE = """<html><body>
<form id="login-form"><button id="signin-btn">Sign in</button></form>
<dialog open><p>cookie banner</p><button id="accept">OK</button></dialog>
</body></html>"""


class FakeBrowser:
    def __init__(self, shadow_dom=False, ready=True, page=PAGE):
        self.shadow_dom = shadow_dom
        self.ready = ready
        self.page = page
        self.clicked = []
        self.scrolled = []

    def get_element_count(self, locator):
        return 1 if "signin-btn" in locator else 0

    def get_element_states(self, locator):
        if "signin-btn" in locator:
            return ["attached", "visible", "enabled"]
        raise AssertionError("unknown element")

    def evaluate_javascript(self, locator, script):
        if "shadowRoot" in script and "some" in script:
            return self.shadow_dom
        if "readyState" in script:
            return self.ready
        if "getBoundingClientRect" in script:
            return "signin" in (locator or "")
        if "processNode" in script:
            return "<html><body>shadow-pierced</body></html>"
        if "tagName" in script:
            return "BUTTON"
        if "innerText" in script:
            return "Sign in"
        raise AssertionError(f"unexpected script: {script[:40]}")

    def get_attribute(self, locator, attr):
        return {"id": "signin-btn", "type": "submit"}.get(attr)

    def get_page_source(self):
        return self.page

    def scroll_to_element(self, locator):
        self.scrolled.append(locator)

    def click(self, locator):
        self.clicked.append(locator)


def test_satisfies_protocol():
    assert isinstance(BrowserDriver(FakeBrowser()), SessionDriver)


def test_count_and_visibility():
    driver = BrowserDriver(FakeBrowser())
    assert driver.count("id=signin-btn") == 1
    assert driver.count("id=missing") == 0
    assert driver.is_visible("id=signin-btn")
    assert not driver.is_visible("id=missing")  # errors -> False, never raises


def test_page_source_prefers_shadow_pierce_when_present():
    assert "shadow-pierced" in BrowserDriver(FakeBrowser(shadow_dom=True)).get_page_source()
    assert "login-form" in BrowserDriver(FakeBrowser(shadow_dom=False)).get_page_source()


def test_simplified_dom_is_curated():
    out = BrowserDriver(FakeBrowser()).get_simplified_dom()
    assert "signin-btn" in out


def test_element_info():
    info = BrowserDriver(FakeBrowser()).get_element_info("id=signin-btn")
    assert info.tag_name == "BUTTON"
    assert info.attributes["id"] == "signin-btn"
    assert info.inner_text == "Sign in"
    assert info.visible and info.in_viewport


def test_open_dialog_detection():
    assert BrowserDriver(FakeBrowser()).open_dialog_locator() == "dialog[open]"
    no_dialog = FakeBrowser(page="<html><body><p>x</p></body></html>")
    assert BrowserDriver(no_dialog).open_dialog_locator() is None


def test_ready_state_and_wait():
    assert BrowserDriver(FakeBrowser(ready=True)).is_page_ready()
    assert BrowserDriver(FakeBrowser(ready=True)).wait_until_ready(1.0)
    assert not BrowserDriver(FakeBrowser(ready=False)).wait_until_ready(0.6)


def test_scroll_into_view_reports_resulting_visibility():
    fake = FakeBrowser()
    driver = BrowserDriver(fake)
    assert driver.scroll_into_view("id=signin-btn")
    assert fake.scrolled == ["id=signin-btn"]
