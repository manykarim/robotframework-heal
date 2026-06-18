"""Agent runtime: model factory, capability resolution, generic agent builder.

All pydantic-ai model/agent construction is isolated here (plus toolsets in
heal.drivers). Backend quirks discovered experimentally live in
``BACKEND_PRESETS`` — see experiments/minimax-probe/FINDINGS.md:

* MiniMax mishandles forced ``tool_choice`` (intermittent missing tool calls,
  minutes of reasoning). ``openai_supports_tool_choice_required=False`` makes
  tool transport fast and reliable; NativeOutput also works.
* vLLM rejects ``strict: true`` / ``additionalProperties: false`` in tool
  definitions -> ``openai_supports_strict_tool_definition=False``.
* Unknown OpenAI-compatible backends default to PromptedOutput — the only
  transport that worked on every reachable model in the probe matrix.

Verification ALWAYS lives in output validators (works in every output mode);
exploration tools are additive and only registered for ``ToolSupport.RELIABLE``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import NativeOutput, PromptedOutput
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.openai import OpenAIProvider

from .settings import HealSettings, OutputMode, ResolvedModelConfig


class ToolSupport(str, Enum):
    NONE = "none"
    UNRELIABLE = "unreliable"
    RELIABLE = "reliable"


@dataclass(frozen=True)
class ModelCapabilities:
    """Effective capabilities for one agent role, after presets + overrides."""

    tools: ToolSupport = ToolSupport.UNRELIABLE
    structured_output: OutputMode = OutputMode.PROMPTED  # resolved, never AUTO
    vision: bool = False


@dataclass(frozen=True)
class BackendPreset:
    """Experimentally established defaults for a known backend."""

    name: str
    url_marker: str
    profile_overrides: dict[str, Any] = field(default_factory=dict)
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)


BACKEND_PRESETS: tuple[BackendPreset, ...] = (
    BackendPreset(
        name="minimax",
        url_marker="api.minimax.io",
        # Probe 2: forced tool_choice is the root cause of flaky/failed tool output.
        profile_overrides={"openai_supports_tool_choice_required": False},
        capabilities=ModelCapabilities(
            tools=ToolSupport.UNRELIABLE,  # probe: exploration loops unreliable on M2.5
            # Prompted is the mode proven reliable WITH validator retry loops
            # (probe P5); native passed single-shot but not under ModelRetry.
            structured_output=OutputMode.PROMPTED,
            vision=False,
        ),
    ),
    BackendPreset(
        name="vllm",
        url_marker="vllm",
        profile_overrides={"openai_supports_strict_tool_definition": False},
        capabilities=ModelCapabilities(
            tools=ToolSupport.UNRELIABLE,
            structured_output=OutputMode.PROMPTED,
        ),
    ),
    BackendPreset(
        name="openrouter",
        url_marker="openrouter.ai",
        # Probe 3: capability varies per model behind the same endpoint; the
        # only universal floor is prompted output. `heal doctor` can upgrade.
        capabilities=ModelCapabilities(
            tools=ToolSupport.UNRELIABLE,
            structured_output=OutputMode.PROMPTED,
        ),
    ),
    BackendPreset(
        name="ollama",
        url_marker=":11434",  # Ollama's default port
        # Sweep (experiments/ollama-small-models): tool calling is unavailable or
        # unreliable over Ollama's OpenAI-compatible endpoint for ~all models, so
        # the prompted floor is the correct default. `heal doctor` can still probe
        # and `override_capabilities` if a given model proves reliably tool-capable.
        # Capable models heal well in prompted mode (granite3.2:8b/gemma3 ~83-92%).
        capabilities=ModelCapabilities(
            tools=ToolSupport.UNRELIABLE,
            structured_output=OutputMode.PROMPTED,
        ),
    ),
)

#: Capabilities for native pydantic-ai provider strings ("openai:gpt-4o", ...).
_PROVIDER_CAPABILITIES = ModelCapabilities(
    tools=ToolSupport.RELIABLE, structured_output=OutputMode.TOOL, vision=False
)


def find_preset(base_url: str | None) -> BackendPreset | None:
    if not base_url:
        return None
    for preset in BACKEND_PRESETS:
        if preset.url_marker in base_url:
            return preset
    return None


class AgentRuntime:
    """Builds and caches models/agents per role; resolves capabilities.

    Agents are constructed once and reused for the whole run (pydantic-ai
    recommendation; also makes UsageLimits/ledger accounting meaningful).
    """

    def __init__(self, settings: HealSettings):
        self._settings = settings
        self._models: dict[str, Model | str] = {}
        self._capabilities: dict[str, ModelCapabilities] = {}
        self._agents: dict[Any, Agent] = {}

    @property
    def settings(self) -> HealSettings:
        return self._settings

    # ------------------------------------------------------------- resolution

    def capabilities(self, role: str) -> ModelCapabilities:
        if role not in self._capabilities:
            self._capabilities[role] = self._resolve_capabilities(self._settings.role_config(role))
        return self._capabilities[role]

    def override_capabilities(self, role: str, capabilities: ModelCapabilities) -> None:
        """Install probed capabilities (from `heal doctor`) for a role."""
        self._capabilities[role] = capabilities

    def _resolve_capabilities(self, cfg: ResolvedModelConfig) -> ModelCapabilities:
        preset = find_preset(cfg.base_url)
        if preset is not None:
            caps = preset.capabilities
        elif cfg.base_url is None and ":" in cfg.model:
            caps = _PROVIDER_CAPABILITIES  # known pydantic-ai provider
        else:
            caps = ModelCapabilities()  # unknown OpenAI-compatible: safe floor
        if cfg.output_mode is not OutputMode.AUTO:
            caps = ModelCapabilities(
                tools=caps.tools, structured_output=cfg.output_mode, vision=caps.vision
            )
        return caps

    # ----------------------------------------------------------------- models

    def model(self, role: str) -> Model | str:
        if role not in self._models:
            self._models[role] = self._build_model(self._settings.role_config(role))
        return self._models[role]

    def _build_model(self, cfg: ResolvedModelConfig) -> Model | str:
        if not cfg.model:
            raise ValueError(
                f"No model configured for role {cfg.role!r}: set HEAL_MODEL or HEAL_{cfg.role.upper()}_MODEL"
            )
        if cfg.base_url:
            provider = OpenAIProvider(base_url=cfg.base_url, api_key=cfg.api_key)
            model = OpenAIChatModel(cfg.model, provider=provider)
            preset = find_preset(cfg.base_url)
            if preset and preset.profile_overrides:
                # Merge quirk fixes INTO the provider-resolved profile instead of
                # replacing it (a bare override profile would e.g. lose
                # supports_json_schema_output and break NativeOutput).
                merged = model.profile.update(OpenAIModelProfile(**preset.profile_overrides))
                model = OpenAIChatModel(cfg.model, provider=provider, profile=merged)
            return model
        # pydantic-ai provider string, e.g. "openai:gpt-4.1-mini"
        return cfg.model

    # ----------------------------------------------------------------- agents

    def build_agent(
        self,
        role: str,
        schema: type[BaseModel],
        *,
        system_prompt: str = "",
        tools: Sequence[Callable[..., Any]] = (),
        retries: int | None = None,
        deps_type: type | None = None,
        configure: Callable[[Agent], None] | None = None,
    ) -> Agent:
        """Build (or fetch the cached) agent for a role with ANY output schema.

        The schema is wrapped in the output mode resolved for the role's
        capabilities. Exploration tools are only attached when the role's
        tool support is RELIABLE — verification belongs in output validators,
        which work in every mode. `configure` runs exactly once per cached
        agent (register output validators there); per-transaction state flows
        through `deps`.
        """
        cache_key = (role, schema, system_prompt, tuple(tools), deps_type, configure)
        if cache_key in self._agents:
            return self._agents[cache_key]

        caps = self.capabilities(role)
        attach_tools = list(tools) if caps.tools is ToolSupport.RELIABLE else []
        kwargs: dict[str, Any] = {}
        if deps_type is not None:
            kwargs["deps_type"] = deps_type
        agent = Agent(
            self.model(role),
            output_type=self._wrap_output(schema, caps.structured_output),
            system_prompt=system_prompt,
            tools=attach_tools,
            retries=self._settings.agent_retries if retries is None else retries,
            **kwargs,
        )
        if configure is not None:
            configure(agent)
        self._agents[cache_key] = agent
        return agent

    @staticmethod
    def _wrap_output(schema: type[BaseModel], mode: OutputMode):
        if mode is OutputMode.NATIVE:
            return NativeOutput(schema)
        if mode is OutputMode.PROMPTED:
            return PromptedOutput(schema)
        return schema  # TOOL (pydantic-ai default transport)
