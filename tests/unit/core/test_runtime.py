import pytest
from pydantic import BaseModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.output import NativeOutput, PromptedOutput

from heal.core.runtime import (
    AgentRuntime,
    ModelCapabilities,
    ToolSupport,
    find_preset,
)
from heal.core.settings import HealSettings, OutputMode


class Out(BaseModel):
    value: str


@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    # provider-string agents instantiate the OpenAI client at construction
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def settings(**kwargs) -> HealSettings:
    return HealSettings(_env_file=None, **kwargs)


def test_find_preset():
    assert find_preset("https://api.minimax.io/v1").name == "minimax"
    assert find_preset("https://openrouter.ai/api/v1").name == "openrouter"
    assert find_preset("http://my-vllm.internal:8000/v1").name == "vllm"
    assert find_preset("https://api.example.com/v1") is None
    assert find_preset(None) is None


def test_capabilities_minimax_preset():
    rt = AgentRuntime(settings(model="MiniMax-M2.5", base_url="https://api.minimax.io/v1"))
    caps = rt.capabilities("triage")
    # prompted: the only mode probe-proven reliable under ModelRetry loops (P5)
    assert caps.structured_output is OutputMode.PROMPTED
    assert caps.tools is ToolSupport.UNRELIABLE


def test_capabilities_unknown_backend_floor():
    rt = AgentRuntime(settings(model="some-model", base_url="https://llm.corp.example/v1"))
    caps = rt.capabilities("locator")
    assert caps.structured_output is OutputMode.PROMPTED
    assert caps.tools is ToolSupport.UNRELIABLE


def test_capabilities_provider_string():
    rt = AgentRuntime(settings(model="openai:gpt-4.1-mini"))
    caps = rt.capabilities("rca")
    assert caps.structured_output is OutputMode.TOOL
    assert caps.tools is ToolSupport.RELIABLE


def test_explicit_output_mode_wins_over_preset():
    rt = AgentRuntime(
        settings(
            model="MiniMax-M2.5",
            base_url="https://api.minimax.io/v1",
            locator_output_mode=OutputMode.NATIVE,
        )
    )
    assert rt.capabilities("locator").structured_output is OutputMode.NATIVE
    assert rt.capabilities("triage").structured_output is OutputMode.PROMPTED


def test_model_building_applies_minimax_profile_fix():
    rt = AgentRuntime(settings(model="MiniMax-M2.5", base_url="https://api.minimax.io/v1", api_key="k"))
    model = rt.model("triage")
    assert isinstance(model, OpenAIChatModel)
    assert model.profile.openai_supports_tool_choice_required is False
    # regression: preset must MERGE into the provider-resolved profile, not
    # replace it — NativeOutput support must survive (live doctor run caught this)
    assert model.profile.supports_json_schema_output is True


def test_model_building_provider_string_passthrough():
    rt = AgentRuntime(settings(model="openai:gpt-4.1-mini"))
    assert rt.model("triage") == "openai:gpt-4.1-mini"


def test_missing_model_raises_actionable_error():
    rt = AgentRuntime(settings())
    with pytest.raises(ValueError, match="HEAL_LOCATOR_MODEL"):
        rt.model("locator")


def test_output_wrapping():
    assert isinstance(AgentRuntime._wrap_output(Out, OutputMode.NATIVE), NativeOutput)
    assert isinstance(AgentRuntime._wrap_output(Out, OutputMode.PROMPTED), PromptedOutput)
    assert AgentRuntime._wrap_output(Out, OutputMode.TOOL) is Out


def test_agent_cached_per_role_and_schema():
    rt = AgentRuntime(settings(model="openai:gpt-4.1-mini"))
    a1 = rt.build_agent("triage", Out, system_prompt="x")
    a2 = rt.build_agent("triage", Out, system_prompt="x")
    a3 = rt.build_agent("rca", Out, system_prompt="x")
    assert a1 is a2 and a1 is not a3


def exploration_tool(query: str) -> str:
    """Pretend DOM query."""
    exploration_tool.calls.append(query)
    return "0 matches"


def run_with_test_model(rt: AgentRuntime, role: str):
    exploration_tool.calls = []
    agent = rt.build_agent(role, Out, tools=[exploration_tool])
    with agent.override(model=TestModel()):
        agent.run_sync("go")
    return exploration_tool.calls


def test_tools_attached_only_when_reliable():
    # TestModel calls every registered tool once: tool attached <=> 1 call
    reliable = AgentRuntime(settings(model="openai:gpt-4.1-mini"))
    assert len(run_with_test_model(reliable, "locator")) == 1

    # unknown backend keeps unreliable tool support; output mode pinned to TOOL
    # so TestModel can complete the run (prompted JSON is not TestModel-able)
    unreliable = AgentRuntime(
        settings(
            model="some-model",
            base_url="https://llm.corp.example/v1",
            api_key="k",
            locator_output_mode=OutputMode.TOOL,
        )
    )
    assert len(run_with_test_model(unreliable, "locator")) == 0


def test_probed_capability_override():
    rt = AgentRuntime(settings(model="m", base_url="https://llm.corp.example/v1", api_key="k"))
    rt.override_capabilities(
        "locator", ModelCapabilities(tools=ToolSupport.RELIABLE, structured_output=OutputMode.TOOL)
    )
    assert len(run_with_test_model(rt, "locator")) == 1
