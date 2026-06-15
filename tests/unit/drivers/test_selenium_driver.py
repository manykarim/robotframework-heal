"""SeleniumDriver conformance tests with a fake webdriver."""

from heal.drivers.protocol import SessionDriver
from heal.drivers.selenium import SeleniumDriver, to_by, to_selenium_locator

PAGE = """<html><body>
<form id="login-form"><button id="signin-btn">Sign in</button>
<input id="user-email" required value=""/></form>
<dialog open><button>OK</button></dialog>
<iframe id="ad" src="x.html"></iframe>
</body></html>"""


class FakeElement:
    def __init__(self, tag="button", displayed=True, attrs=None, text="Sign in"):
        self.tag_name = tag
        self._displayed = displayed
        self._attrs = attrs or {"id": "signin-btn"}
        self.text = text
        self.actions = []

    def is_displayed(self):
        return self._displayed

    def get_attribute(self, name):
        return self._attrs.get(name)

    def clear(self):
        self.actions.append("clear")

    def send_keys(self, value):
        self.actions.append(("keys", value))

    def click(self):
        self.actions.append("click")


class FakeWebDriver:
    def __init__(self):
        self.page_source = PAGE
        self.elements = {("css selector", "#signin-btn"): [FakeElement()]}
        self.scripts = []

    def find_elements(self, by, value):
        return self.elements.get((by, value), [])

    def execute_script(self, script, *args):
        self.scripts.append(script)
        if "readyState" in script:
            return "complete"
        if "innerText" in script:
            return "Sign in"
        if "getBoundingClientRect" in script:
            return True
        if "ser(document" in script:
            return self.page_source
        return None

    def get_screenshot_as_png(self):
        return b"\x89PNG-fake"


class FakeSeleniumLibrary:
    def __init__(self):
        self.driver = FakeWebDriver()


def test_locator_translation():
    assert to_by("css=#a") == ("css selector", "#a")
    assert to_by("css:#a") == ("css selector", "#a")
    assert to_by("xpath=//b") == ("xpath", "//b")
    assert to_by("//b[1]") == ("xpath", "//b[1]")
    assert to_by("id=x") == ("id", "x")
    assert to_by("plain") == ("css selector", "plain")
    assert to_selenium_locator("css=#a") == "css:#a"
    assert to_selenium_locator("xpath=//b") == "xpath://b"


def test_protocol_conformance_and_queries():
    driver = SeleniumDriver(FakeSeleniumLibrary())
    assert isinstance(driver, SessionDriver)
    assert driver.count("css=#signin-btn") == 1
    assert driver.count("css=#missing") == 0
    assert driver.is_visible("css=#signin-btn")
    assert driver.is_in_viewport("css=#signin-btn") is True
    assert driver.is_page_ready()
    info = driver.get_element_info("css=#signin-btn")
    assert info.tag_name == "BUTTON" and info.attributes["id"] == "signin-btn"
    assert driver.take_screenshot().startswith(b"\x89PNG")


def test_inspections_from_page_source():
    driver = SeleniumDriver(FakeSeleniumLibrary())
    assert driver.open_dialog_locator() == "css=dialog[open]"
    assert any("user-email" in issue for issue in driver.find_form_issues())
    dom = driver.get_simplified_dom()
    assert "CANNOT reach elements inside frames" in dom  # frame-limitation note


def test_actions():
    lib = FakeSeleniumLibrary()
    driver = SeleniumDriver(lib)
    element = lib.driver.elements[("css selector", "#signin-btn")][0]
    driver.fill_text("css=#signin-btn", "hello")
    assert element.actions == ["clear", ("keys", "hello")]
    driver.click("css=#signin-btn")
    assert element.actions[-1] == "click"
    assert driver.scroll_into_view("css=#signin-btn")
    assert driver.wait_until_ready(1.0)
