"""Locator-drift healing: validator-verified proposals, retry feedback, rerun."""

import asyncio
import json

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from heal.core.agents.locator import get_locator_agent
from heal.core.engine import HealingEngine
from heal.core.evidence import ContextBuilder
from heal.core.runtime import AgentRuntime
from heal.core.schemas import FailureClass, KeywordCall, OutcomeStatus
from heal.core.settings import HealSettings, OutputMode


class FakeDriver:
    """Page with exactly one signin button; broken locator matches nothing."""

    def __init__(self):
        self.counts = {"id=login": 0, "css=#signin-btn": 1, "css=.btn": 3, "css=#ghost": 0}
        self.visible = {"css=#signin-btn": True}

    def is_page_ready(self):
        return True

    def count(self, locator):
        return self.counts.get(locator, 0)

    def is_visible(self, locator):
        return self.visible.get(locator, False)

    def is_in_viewport(self, locator):
        return True

    def open_dialog_locator(self):
        return None

    def get_simplified_dom(self):
        return "<body><form id='login-form'><button id='signin-btn'>Sign in</button></form></body>"

    def take_screenshot(self):
        return None


class FakeSession:
    def __init__(self, driver, fail_first_rerun=False):
        self.driver = driver
        self.reruns = []
        self.fail_first_rerun = fail_first_rerun

    def rerun_keyword(self, keyword, *, locator_override=None):
        self.reruns.append(locator_override)
        if self.fail_first_rerun and len(self.reruns) == 1:
            raise AssertionError("element detached during rerun")
        return "rerun-value"


def proposals_model(rounds):
    """FunctionModel emitting one LocatorProposals JSON per validation round."""
    state = {"i": 0}

    def respond(messages, info: AgentInfo):
        payload = rounds[min(state["i"], len(rounds) - 1)]
        state["i"] += 1
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(respond)


def make_engine():
    settings = HealSettings(
        _env_file=None, model="openai:gpt-4.1-mini", locator_output_mode=OutputMode.PROMPTED
    )
    return HealingEngine(AgentRuntime(settings))


def make_builder(driver):
    return ContextBuilder(
        keyword=KeywordCall(
            name="Click", args=["id=login"], owner_library="Browser", lineno=12, source="/suite/login.robot"
        ),
        error_message="TimeoutError: waiting for locator('id=login')",
        test_name="T",
        suite_name="S",
        failed_locator="id=login",
        driver=driver,
    )


@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def heal(engine, model, driver=None, session=None):
    driver = driver or FakeDriver()
    session = session or FakeSession(driver)
    agent = get_locator_agent(engine.runtime)
    with agent.override(model=model):
        event = asyncio.run(engine.handle(make_builder(driver), session))
    return event, session


def test_heal_with_verified_locator():
    model = proposals_model([{"locators": ["css=#signin-btn"], "rationale": "id present"}])
    event, session = heal(make_engine(), model)
    assert event.outcome.status is OutcomeStatus.HEALED
    assert event.outcome.healed_locator == "css=#signin-btn"
    assert session.reruns == ["css=#signin-btn"]
    assert event.outcome.return_value_repr == "'rerun-value'"
    assert event.fix_proposal.new_value == "css=#signin-btn"
    assert event.fix_proposal.old_value == "id=login"


def test_invalid_proposals_bounced_until_verified():
    model = proposals_model(
        [
            {"locators": ["css=#ghost", "css=.btn"], "rationale": "guess"},  # 0 and 3 matches
            {"locators": ["css=#signin-btn"], "rationale": "corrected"},
        ]
    )
    event, session = heal(make_engine(), model)
    assert event.outcome.status is OutcomeStatus.HEALED
    assert session.reruns == ["css=#signin-btn"]


def test_all_proposals_invalid_ends_unhealed():
    model = proposals_model([{"locators": ["css=#ghost"], "rationale": "bad"}])
    event, session = heal(make_engine(), model)
    assert event.outcome.status is OutcomeStatus.UNHEALED
    assert session.reruns == []
    assert event.outcome.diagnosis.failure_class is FailureClass.LOCATOR_DRIFT
    assert "verification" in event.outcome.detail
    assert event.fix_proposal is None
    assert event.rca.clean_message


def test_rerun_failure_falls_through_to_next_candidate():
    driver = FakeDriver()
    driver.counts["css=#login-form button"] = 1
    driver.visible["css=#login-form button"] = True
    model = proposals_model(
        [{"locators": ["css=#login-form button", "css=#signin-btn"], "rationale": "two options"}]
    )
    event, session = heal(make_engine(), model, driver=driver, session=FakeSession(driver, fail_first_rerun=True))
    assert event.outcome.status is OutcomeStatus.HEALED
    assert session.reruns == ["css=#login-form button", "css=#signin-btn"]
    assert event.outcome.healed_locator == "css=#signin-btn"
    assert [a.succeeded for a in event.outcome.attempts] == [False, True]


def test_ambiguous_locator_detected_and_disambiguated():
    driver = FakeDriver()
    driver.counts["id=login"] = 6  # ambiguous now
    driver.counts["css=.btn:visible"] = 1
    driver.visible["css=.btn:visible"] = True

    def disambiguate(locator):
        return f"{locator}:visible" if driver.counts.get(f"{locator}:visible") else None

    driver.disambiguate = disambiguate
    engine = make_engine()
    model = proposals_model([{"locators": ["css=.btn"], "rationale": "refinable"}])
    builder = ContextBuilder(
        keyword=KeywordCall(name="Click", args=["id=login"], owner_library="Browser", lineno=12, source=None),
        error_message="Error: strict mode violation: locator('id=login') resolved to 6 elements",
        failed_locator="id=login",
        driver=driver,
    )
    session = FakeSession(driver)
    agent = get_locator_agent(engine.runtime)
    with agent.override(model=model):
        event = asyncio.run(engine.handle(builder, session))
    assert event.outcome.diagnosis.failure_class is FailureClass.LOCATOR_DRIFT
    assert "ambiguous" in event.outcome.diagnosis.rationale
    assert event.outcome.status is OutcomeStatus.HEALED
    assert event.outcome.healed_locator == "css=.btn:visible"


def test_type_incompatible_proposal_rejected_until_select():
    driver = FakeDriver()
    driver.counts.update({"css=label.model": 1, "css=select#model": 1})
    driver.visible.update({"css=label.model": True, "css=select#model": True})
    tags = {"css=label.model": "LABEL", "css=select#model": "SELECT"}

    from heal.drivers.protocol import ElementInfo

    driver.get_element_info = lambda loc: ElementInfo(locator=loc, tag_name=tags.get(loc, ""))
    model = proposals_model(
        [
            {"locators": ["css=label.model"], "rationale": "wrong tag"},
            {"locators": ["css=select#model"], "rationale": "corrected to select"},
        ]
    )
    builder = ContextBuilder(
        keyword=KeywordCall(
            name="Select Options By", args=["id=login", "text", "Rassant"], owner_library="Browser"
        ),
        error_message="TimeoutError: waiting for locator('id=login')",
        failed_locator="id=login",
        driver=driver,
    )
    engine = make_engine()
    session = FakeSession(driver)
    agent = get_locator_agent(engine.runtime)
    with agent.override(model=model):
        event = asyncio.run(engine.handle(builder, session))
    assert event.outcome.status is OutcomeStatus.HEALED
    assert event.outcome.healed_locator == "css=select#model"
