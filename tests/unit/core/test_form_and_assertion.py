"""Form-state diagnosis, assertion-drift healing, RCA enrichment."""

import asyncio
import json

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from heal.core.agents import rca as rca_module
from heal.core.classes.assertion_drift import parse_assertion, semantic_guard
from heal.core.engine import HealingEngine
from heal.core.evidence import ContextBuilder
from heal.core.runtime import AgentRuntime
from heal.core.schemas import FailureClass, KeywordCall, OutcomeStatus
from heal.core.settings import HealSettings, OutputMode


class FormDriver:
    def __init__(self, issues=None):
        self.issues = issues if issues is not None else ["required field 'user-email' is empty"]
        self.filled = []

    def is_page_ready(self):
        return True

    def count(self, locator):
        return 1

    def is_in_viewport(self, locator):
        return True

    def open_dialog_locator(self):
        return None

    def get_simplified_dom(self):
        return "<body><form/></body>"

    def take_screenshot(self):
        return None

    def find_form_issues(self):
        return self.issues

    def fill_text(self, locator, value):
        self.filled.append((locator, value))
        self.issues = []


class Session:
    def __init__(self, driver):
        self.driver = driver
        self.reruns = []

    def rerun_keyword(self, keyword, *, locator_override=None):
        self.reruns.append(keyword.args)
        return "ok"


@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def make_engine(**kwargs):
    return HealingEngine(AgentRuntime(HealSettings(_env_file=None, model="openai:gpt-4.1-mini", **kwargs)))


def run_failure(engine, driver, error="TimeoutError: waiting for navigation", keyword="Click", args=("id=submit",)):
    builder = ContextBuilder(
        keyword=KeywordCall(name=keyword, args=list(args), owner_library="Browser"),
        error_message=error,
        failed_locator=args[0] if args else None,
        driver=driver,
    )
    session = Session(driver)
    return asyncio.run(engine.handle(builder, session)), session


def test_form_state_diagnose_only_by_default():
    event, session = run_failure(make_engine(), FormDriver())
    assert event.outcome.diagnosis.failure_class is FailureClass.FORM_STATE
    assert event.outcome.status is OutcomeStatus.UNHEALED
    assert "user-email" in event.outcome.detail
    assert "HEAL_FORM_FILL" in event.outcome.detail
    assert session.reruns == []  # nothing touched the page


def test_form_fill_opt_in_records_values():
    driver = FormDriver()
    event, session = run_failure(make_engine(form_fill=True), driver)
    assert event.outcome.status is OutcomeStatus.HEALED
    assert driver.filled and driver.filled[0][1] == "heal-test@example.com"
    fill_attempts = [a for a in event.outcome.attempts if a.action.type.value == "fill"]
    assert fill_attempts and fill_attempts[0].action.params["value"] == "heal-test@example.com"
    assert session.reruns  # rerun happened after fill


def test_parse_assertion_variants():
    assert parse_assertion("Text 'Save changes' should be 'Save'") == ("Save changes", "Save")
    assert parse_assertion("'a' != 'b'") == ("a", "b")
    assert parse_assertion("no assertion here") is None


def test_semantic_guard_magnitude_and_disjoint():
    assert semantic_guard("5 items", "500 items") is not None
    assert semantic_guard("Save", "Completely different words entirely") is not None
    assert semantic_guard("Save", "Save changes") is None


def test_assertion_drift_disabled_by_default():
    event, session = run_failure(
        make_engine(), FormDriver(issues=[]),
        error="Text 'Save changes' should be 'Save'", keyword="Get Text", args=("id=btn", "==", "Save"),
    )
    assert event.outcome.diagnosis.failure_class is FailureClass.ASSERTION_DRIFT
    assert event.outcome.status is OutcomeStatus.UNHEALED
    assert "HEAL_ASSERTIONS" in event.outcome.detail
    assert session.reruns == []


def test_assertion_drift_healed_with_verified_rerun():
    event, session = run_failure(
        make_engine(heal_assertions=True), FormDriver(issues=[]),
        error="Text 'Save changes' should be 'Save'", keyword="Get Text", args=("id=btn", "==", "Save"),
    )
    assert event.outcome.status is OutcomeStatus.HEALED
    assert session.reruns == [["id=btn", "==", "Save changes"]]
    assert "Save changes" in event.outcome.detail


def test_assertion_semantic_drift_refused():
    event, session = run_failure(
        make_engine(heal_assertions=True), FormDriver(issues=[]),
        error="Text '500 items' should be '5 items'", keyword="Get Text", args=("id=count", "==", "5 items"),
    )
    assert event.outcome.status is OutcomeStatus.UNHEALED
    assert "refused" in event.outcome.detail.lower()
    assert session.reruns == []


def test_rca_enrichment_replaces_template():
    engine = make_engine(rca_output_mode=OutputMode.PROMPTED)

    def respond(messages, info: AgentInfo):
        payload = {
            "clean_message": "The login button was renamed during the redesign.",
            "root_cause": "App change on 2026-06-01",
            "suggested_fix": "Update login.robot:12",
        }
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    agent = engine.runtime.build_agent("rca", rca_module.RcaDraft, system_prompt=rca_module.SYSTEM_PROMPT)
    driver = FormDriver()
    with agent.override(model=FunctionModel(respond)):
        event, _ = run_failure(engine, driver)
    assert event.rca.clean_message == "The login button was renamed during the redesign."
    assert event.rca.suggested_fix == "Update login.robot:12"
    assert event.rca.failure_class is FailureClass.FORM_STATE  # template fields preserved


def test_parse_assertion_rf_typed_message():
    actual, expected = parse_assertion("Text '1 item left!' (str) should be '0 items left!' (str)")
    assert (actual, expected) == ("1 item left!", "0 items left!")
