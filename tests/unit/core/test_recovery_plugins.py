"""Viewport and overlay healing, including the Appium swipe-search fallthrough."""

import asyncio

import pytest

from heal.core.engine import HealingEngine
from heal.core.evidence import ContextBuilder
from heal.core.runtime import AgentRuntime
from heal.core.schemas import FailureClass, KeywordCall, OutcomeStatus
from heal.core.settings import HealSettings


class WebDriver:
    dom_covers_viewport_only = False

    def __init__(self, *, counts=None, in_viewport=False, dialog=None, dismissibles=None):
        self.counts = counts or {}
        self.in_viewport = in_viewport
        self.dialog = dialog
        self.dismissibles = dismissibles or []
        self.scrolled, self.clicked = [], []

    def is_page_ready(self):
        return True

    def count(self, locator):
        return self.counts.get(locator, 0)

    def is_in_viewport(self, locator):
        return self.in_viewport

    def open_dialog_locator(self):
        return self.dialog

    def find_dismiss_controls(self):
        return self.dismissibles

    def get_simplified_dom(self):
        return "<body/>"

    def take_screenshot(self):
        return None

    def scroll_into_view(self, locator):
        self.scrolled.append(locator)
        return True

    def click(self, locator):
        self.clicked.append(locator)
        self.dialog = None  # dismissal works


class MobileDriver(WebDriver):
    dom_covers_viewport_only = True

    def __init__(self, *, find_on_swipe=True, **kwargs):
        super().__init__(**kwargs)
        self.find_on_swipe = find_on_swipe

    def scroll_into_view(self, locator):
        self.scrolled.append(locator)
        if self.find_on_swipe:
            self.counts[locator] = 1
            return True
        return False


class Session:
    def __init__(self, driver, rerun_ok=True):
        self.driver = driver
        self.reruns = []
        self.rerun_ok = rerun_ok

    def rerun_keyword(self, keyword, *, locator_override=None):
        self.reruns.append((keyword.name, locator_override))
        if not self.rerun_ok:
            raise AssertionError("still failing")
        return "ok"


@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def run_failure(driver, locator="id=item"):
    engine = HealingEngine(AgentRuntime(HealSettings(_env_file=None, model="openai:gpt-4.1-mini")))
    builder = ContextBuilder(
        keyword=KeywordCall(name="Click", args=[locator], owner_library="Browser"),
        error_message="element is not visible",
        failed_locator=locator,
        driver=driver,
    )
    return asyncio.run(engine.handle(builder, Session(driver))), driver


def test_web_viewport_scroll_heal():
    event, driver = run_failure(WebDriver(counts={"id=item": 1}, in_viewport=False))
    assert event.outcome.diagnosis.failure_class is FailureClass.VIEWPORT
    assert event.outcome.status is OutcomeStatus.HEALED
    assert driver.scrolled == ["id=item"]


def test_mobile_offscreen_swipe_heal():
    event, driver = run_failure(MobileDriver(counts={"id=item": 0}, find_on_swipe=True))
    assert event.outcome.diagnosis.failure_class is FailureClass.VIEWPORT
    assert event.outcome.status is OutcomeStatus.HEALED
    assert "swipe search" in event.outcome.detail


def test_mobile_swipe_exhausted_falls_through_to_locator_drift():
    driver = MobileDriver(counts={"id=item": 0}, find_on_swipe=False)
    engine = HealingEngine(AgentRuntime(HealSettings(_env_file=None, model="openai:gpt-4.1-mini")))
    builder = ContextBuilder(
        keyword=KeywordCall(name="Click", args=["id=item"], owner_library="AppiumLibrary"),
        error_message="did not match any elements",
        failed_locator="id=item",
        driver=driver,
    )
    event = asyncio.run(engine.handle(builder, Session(driver)))
    # fell through: locator-drift heal ran (agent fails without LLM -> unhealed)
    assert event.outcome.status is OutcomeStatus.UNHEALED
    # the swipe attempt from the viewport plugin is preserved in the merged attempts
    assert any("swipe search" in a.action.description for a in event.outcome.attempts)


def test_overlay_dismiss_and_rerun():
    driver = WebDriver(
        counts={"id=item": 1},
        in_viewport=True,
        dialog="dialog[open]",
        dismissibles=['dialog[open] button:has-text("ok")'],
    )
    event, driver = run_failure(driver)
    assert event.outcome.diagnosis.failure_class is FailureClass.OVERLAY
    assert event.outcome.status is OutcomeStatus.HEALED
    assert driver.clicked == ['dialog[open] button:has-text("ok")']


def test_overlay_without_dismiss_control_falls_through_to_locator():
    driver = WebDriver(counts={"id=item": 1}, in_viewport=True, dialog="dialog[open]", dismissibles=[])
    event, _ = run_failure(driver)
    assert event.outcome.status is OutcomeStatus.UNHEALED
    # the dialog may be unrelated -> locator healing gets a go (and fails LLM-less here)
    assert event.outcome.diagnosis.failure_class is FailureClass.LOCATOR_DRIFT
    assert "fallthrough from overlay" in event.outcome.diagnosis.rationale
