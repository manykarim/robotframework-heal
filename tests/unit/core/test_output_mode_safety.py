"""The doctor-probe safety rule: never heal in a mode the endpoint can't produce.

Cases are taken from experiments/small-model-sweep/FINDINGS.md, where a preset
pinned to prompted output took qwen3-8b from 95% (native) to 0%.
"""

import asyncio

import pytest

from heal.core.doctor import probe_output_modes, safe_output_mode
from heal.core.runtime import AgentRuntime, ModelCapabilities, ToolSupport
from heal.core.settings import HealSettings, OutputMode

PROMPTED, NATIVE, TOOL = OutputMode.PROMPTED, OutputMode.NATIVE, OutputMode.TOOL


def settings(**kw):
    kw.setdefault("model", "m")
    return HealSettings(_env_file=None, **kw)


@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


# --------------------------------------------------------------- the rule

def test_working_mode_is_never_second_guessed():
    """gemma-3-4b passes both probes but heals 75% prompted vs 35% native.

    A probe says a transport works, not that it works *better* -- so a passing
    preference must survive even when another mode also passes.
    """
    working = {PROMPTED: True, NATIVE: True}
    assert safe_output_mode(working, PROMPTED) is PROMPTED
    assert safe_output_mode(working, NATIVE) is NATIVE


def test_broken_mode_falls_back_to_one_that_works():
    # the qwen3-8b case: prompted times out on every heal, native scores 95%
    working = {PROMPTED: False, NATIVE: True, TOOL: False}
    assert safe_output_mode(working, PROMPTED) is NATIVE


def test_fallback_prefers_tool_then_native():
    assert safe_output_mode({PROMPTED: False, NATIVE: True, TOOL: True}, PROMPTED) is TOOL
    assert safe_output_mode({PROMPTED: False, NATIVE: True, TOOL: False}, PROMPTED) is NATIVE


def test_unprobed_mode_is_left_alone():
    assert safe_output_mode({}, PROMPTED) is PROMPTED


def test_nothing_works_keeps_the_configured_choice():
    working = {PROMPTED: False, NATIVE: False, TOOL: False}
    assert safe_output_mode(working, PROMPTED) is PROMPTED


# ------------------------------------------------------- targeted probing

def test_probe_stops_after_the_preferred_mode_works():
    """One tiny call in the common case -- the cost of defaulting this on."""
    calls = []

    async def fake(name, coro):
        calls.append(name)
        coro.close()
        from heal.core.doctor import ProbeResult

        return ProbeResult(name=name, ok=True)

    import heal.core.doctor as doctor

    original = doctor._run_probe
    doctor._run_probe = fake
    try:
        working = asyncio.run(probe_output_modes("openai:gpt-4.1-mini", PROMPTED))
    finally:
        doctor._run_probe = original
    assert calls == ["prompted_output"]
    assert working == {PROMPTED: True}


def test_probe_seeks_a_fallback_only_after_failure():
    from heal.core.doctor import ProbeResult

    async def fake(name, coro):
        coro.close()
        return ProbeResult(name=name, ok=(name == "native_output"))

    import heal.core.doctor as doctor

    original = doctor._run_probe
    doctor._run_probe = fake
    try:
        working = asyncio.run(probe_output_modes("openai:gpt-4.1-mini", PROMPTED))
    finally:
        doctor._run_probe = original
    assert working[PROMPTED] is False
    assert working[NATIVE] is True
    assert safe_output_mode(working, PROMPTED) is NATIVE


# ------------------------------------------------------------- the runtime

def test_runtime_switches_mode_and_records_a_note():
    rt = AgentRuntime(settings(base_url="http://host:11434/v1", api_key="k"))
    assert rt.capabilities("locator").structured_output is PROMPTED  # ollama preset

    caps = rt._apply_safe_mode(
        "locator", rt.capabilities("locator"), {PROMPTED: False, NATIVE: True}
    )
    assert caps.structured_output is NATIVE
    assert rt.capabilities("locator").structured_output is NATIVE  # cached
    assert rt.capability_notes and "prompted" in rt.capability_notes[0]


def test_runtime_keeps_tools_and_vision_when_correcting_mode():
    rt = AgentRuntime(settings(base_url="http://host:11434/v1", api_key="k"))
    rt.override_capabilities(
        "locator", ModelCapabilities(tools=ToolSupport.RELIABLE, structured_output=PROMPTED, vision=True)
    )
    caps = rt._apply_safe_mode("locator", rt.capabilities("locator"), {PROMPTED: False, NATIVE: True})
    assert caps.structured_output is NATIVE
    assert caps.tools is ToolSupport.RELIABLE  # the rule is about output mode only
    assert caps.vision is True


def test_correcting_mode_evicts_agents_cached_under_the_old_mode():
    from pydantic import BaseModel

    class Out(BaseModel):
        value: str

    rt = AgentRuntime(settings(model="openai:gpt-4.1-mini"))
    rt.override_capabilities("locator", ModelCapabilities(structured_output=PROMPTED))
    rt.build_agent("locator", Out)
    assert rt._agents, "agent should be cached"

    rt._apply_safe_mode("locator", rt.capabilities("locator"), {PROMPTED: False, NATIVE: True})
    assert not any(k[0] == "locator" for k in rt._agents), "stale agent kept the broken mode"


def test_probe_disabled_makes_it_a_no_op():
    rt = AgentRuntime(settings(base_url="http://host:11434/v1", api_key="k", probe_capabilities=False))
    caps = asyncio.run(rt.ensure_safe_output_mode("locator"))
    assert caps.structured_output is PROMPTED
    assert rt._probed_modes == {}  # nothing was probed, so nothing was spent


def test_probe_skipped_when_no_model_configured():
    rt = AgentRuntime(HealSettings(_env_file=None, model=""))
    caps = asyncio.run(rt.ensure_safe_output_mode("locator"))
    assert caps is not None
    assert rt._probed_modes == {}


def test_probe_result_is_cached_per_endpoint_not_per_role():
    """Roles sharing one HEAL_MODEL must cost a single probe for the whole run."""
    rt = AgentRuntime(settings(base_url="http://host:11434/v1", api_key="k"))
    probes = []

    async def fake_probe(model, preferred, **kw):
        probes.append(preferred)
        return {PROMPTED: True}

    import heal.core.doctor as doctor

    original = doctor.probe_output_modes
    doctor.probe_output_modes = fake_probe
    try:
        asyncio.run(rt.ensure_safe_output_mode("locator"))
        asyncio.run(rt.ensure_safe_output_mode("triage"))
        asyncio.run(rt.ensure_safe_output_mode("rca"))
    finally:
        doctor.probe_output_modes = original
    assert len(probes) == 1


@pytest.mark.parametrize("mode", [PROMPTED, NATIVE, TOOL])
def test_explicit_output_mode_still_gets_the_safety_net(mode):
    """An explicit HEAL_OUTPUT_MODE is a preference, not a suicide pact."""
    rt = AgentRuntime(settings(base_url="http://h/v1", api_key="k", output_mode=mode))
    assert rt.capabilities("locator").structured_output is mode
    working = {m: (m is NATIVE) for m in (PROMPTED, NATIVE, TOOL)}
    caps = rt._apply_safe_mode("locator", rt.capabilities("locator"), working)
    assert caps.structured_output is NATIVE
