"""Engine pipeline tests: detector path, triage fallback, budgets, timing heal.

LLM-free: the triage agent runs against FunctionModel/TestModel via
Agent.override, exercising the real pydantic-ai plumbing.
"""

import asyncio
import json

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from heal.core.agents import triage as triage_module
from heal.core.engine import HealingEngine, default_registry
from heal.core.evidence import ContextBuilder
from heal.core.runtime import AgentRuntime
from heal.core.schemas import (
    EvidenceKind,
    FailureClass,
    KeywordCall,
    OutcomeStatus,
)
from heal.core.session import RerunNotSupported
from heal.core.settings import HealSettings, OutputMode


class FakeDriver:
    """Scriptable SessionDriver stand-in."""

    def __init__(self, *, ready=True, counts=None, in_viewport=True, dialog=None, dom="<body/>"):
        self.ready = ready
        self.counts = counts or {}
        self.in_viewport = in_viewport
        self.dialog = dialog
        self.dom = dom

    def is_page_ready(self):
        return self.ready

    def wait_until_ready(self, timeout):
        self.ready = True
        return True

    def count(self, locator):
        return self.counts.get(locator, 0)

    def is_in_viewport(self, locator):
        return self.in_viewport

    def open_dialog_locator(self):
        return self.dialog

    def get_simplified_dom(self):
        return self.dom

    def take_screenshot(self):
        return None

    def scroll_into_view(self, locator):
        self.in_viewport = True
        return True


class FakeSession:
    def __init__(self, driver, rerun_result="ok", rerun_error=None):
        self.driver = driver
        self.reruns = []
        self.rerun_result = rerun_result
        self.rerun_error = rerun_error

    def rerun_keyword(self, keyword, *, locator_override=None):
        self.reruns.append((keyword.name, locator_override))
        if self.rerun_error:
            raise self.rerun_error
        return self.rerun_result


def make_builder(driver, locator="id=login", error="TimeoutError: waiting for locator"):
    return ContextBuilder(
        keyword=KeywordCall(name="Click", args=[locator], owner_library="Browser", lineno=10, source=None),
        error_message=error,
        test_name="T",
        suite_name="S",
        failed_locator=locator,
        driver=driver,
    )


def make_engine(**settings_kwargs) -> HealingEngine:
    settings = HealSettings(_env_file=None, model="openai:gpt-4.1-mini", **settings_kwargs)
    return HealingEngine(AgentRuntime(settings))


@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def run(coro):
    return asyncio.run(coro)


def test_detector_path_locator_drift_no_llm():
    driver = FakeDriver(counts={"id=login": 0})
    engine = make_engine()
    event = run(engine.handle(make_builder(driver), FakeSession(driver)))
    assert event.outcome.diagnosis.failure_class is FailureClass.LOCATOR_DRIFT
    # no heal strategy yet (phase 4) -> unhealed, but diagnosed without LLM
    assert event.outcome.status is OutcomeStatus.UNHEALED
    assert engine.ledger.total_tokens == 0
    assert event.rca.clean_message
    assert event.event_id == "heal-1"


def test_timing_detector_heals_by_wait_and_rerun():
    driver = FakeDriver(ready=False, counts={"id=login": 1})
    session = FakeSession(driver)
    event = run(make_engine().handle(make_builder(driver), session))
    assert event.outcome.diagnosis.failure_class is FailureClass.TIMING
    assert event.outcome.status is OutcomeStatus.HEALED
    assert session.reruns == [("Click", None)]
    assert any(a.action.type.value == "wait" for a in event.outcome.attempts)


def test_timing_unhealed_when_rerun_not_supported():
    driver = FakeDriver(ready=False)
    session = FakeSession(driver, rerun_error=RerunNotSupported("post-run"))
    event = run(make_engine().handle(make_builder(driver), session))
    assert event.outcome.status is OutcomeStatus.UNHEALED
    assert "cannot rerun" in event.outcome.detail


def test_viewport_detector_heals_by_scrolling():
    driver = FakeDriver(counts={"id=login": 1}, in_viewport=False)
    event = run(make_engine().handle(make_builder(driver), FakeSession(driver)))
    assert event.outcome.diagnosis.failure_class is FailureClass.VIEWPORT
    assert event.outcome.status is OutcomeStatus.HEALED


def test_overlay_beats_viewport_but_not_missing_element():
    blocked = FakeDriver(counts={"id=login": 1}, dialog="dialog[open]", in_viewport=False)
    event = run(make_engine().handle(make_builder(blocked), FakeSession(blocked)))
    assert event.outcome.diagnosis.failure_class is FailureClass.OVERLAY

    gone = FakeDriver(counts={"id=login": 0}, dialog="dialog[open]")
    event = run(make_engine().handle(make_builder(gone), FakeSession(gone)))
    assert event.outcome.diagnosis.failure_class is FailureClass.LOCATOR_DRIFT


def triage_responder(failure_class="assertion-drift"):
    def respond(messages, info: AgentInfo):
        payload = {"failure_class": failure_class, "confidence": "medium", "rationale": "from triage"}
        return ModelResponse(parts=[TextPart(json.dumps(payload))])

    return FunctionModel(respond)


def test_triage_fallback_when_detectors_silent(monkeypatch):
    # element exists, visible, page ready, no dialog -> all detectors silent
    driver = FakeDriver(counts={"id=login": 1}, in_viewport=True)
    engine = make_engine(triage_output_mode=OutputMode.PROMPTED)
    agent = engine.runtime.build_agent("triage", triage_module.Diagnosis, system_prompt=triage_module.SYSTEM_PROMPT)
    with agent.override(model=triage_responder()):
        event = run(engine.handle(make_builder(driver), FakeSession(driver)))
    assert event.outcome.diagnosis.failure_class is FailureClass.ASSERTION_DRIFT
    assert event.outcome.diagnosis.rationale == "from triage"
    assert engine.ledger.total_tokens > 0  # triage usage recorded


def test_triage_agent_failure_degrades_to_unknown():
    driver = FakeDriver(counts={"id=login": 1}, in_viewport=True)
    engine = make_engine(triage_output_mode=OutputMode.PROMPTED)

    def explode(messages, info):
        raise RuntimeError("endpoint down")

    agent = engine.runtime.build_agent("triage", triage_module.Diagnosis, system_prompt=triage_module.SYSTEM_PROMPT)
    with agent.override(model=FunctionModel(explode)):
        event = run(engine.handle(make_builder(driver), FakeSession(driver)))
    assert event.outcome.diagnosis.failure_class is FailureClass.UNKNOWN
    assert "Triage agent unavailable" in event.outcome.diagnosis.rationale
    assert event.outcome.status is OutcomeStatus.UNHEALED


def test_run_budget_exhaustion_suppresses():
    engine = make_engine(max_run_tokens=1)
    engine.ledger.total_tokens = 5
    driver = FakeDriver(counts={"id=login": 0})
    event = run(engine.handle(make_builder(driver), FakeSession(driver)))
    assert event.outcome.status is OutcomeStatus.SUPPRESSED
    assert engine.ledger.suppressed == 1


def test_per_failure_timeout_aborts_transaction():
    class SlowDriver(FakeDriver):
        def is_page_ready(self):
            import time

            time.sleep(2)
            return True

    engine = make_engine(max_failure_seconds=0.3)
    driver = SlowDriver(counts={"id=login": 0})
    event = run(engine.handle(make_builder(driver), FakeSession(driver)))
    assert event.outcome.status is OutcomeStatus.UNHEALED
    assert "time budget" in event.outcome.diagnosis.rationale


def test_triage_prompt_uses_curated_evidence():
    ctx = make_builder(FakeDriver(dom="<body><form id='login-form'/></body>")).context(
        EvidenceKind.DOM_EXCERPT
    )
    prompt = triage_module.build_user_prompt(ctx)
    assert "login-form" in prompt
    assert "failed_locator: id=login" in prompt
