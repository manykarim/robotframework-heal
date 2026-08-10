"""Endpoint capability probing — the library behind `heal doctor`.

Fires minimal calls at a configured model to establish what actually works
(tool-based output, native JSON schema, prompted JSON, exploration tool calls,
vision), then resolves a `ModelCapabilities` profile plus human-readable
recommendations. Probing replaces assumptions: the experiment matrix showed
capability varies per model behind the same endpoint and error kinds differ
(transport vs quality vs availability).
"""

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass, field

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models import Model
from pydantic_ai.output import NativeOutput, PromptedOutput

from .runtime import ModelCapabilities, ToolSupport
from .settings import OutputMode

PROBE_TIMEOUT_SECONDS = 90.0

#: 1x1 white PNG — enough to test image-input transport.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)


class _Probe(BaseModel):
    """Flat probe schema (austerity rule applies to probes too)."""

    answer: str


@dataclass
class ProbeResult:
    name: str
    ok: bool
    latency_seconds: float = 0.0
    error: str = ""


@dataclass
class DoctorReport:
    model_name: str
    results: list[ProbeResult] = field(default_factory=list)

    def result(self, name: str) -> ProbeResult | None:
        return next((r for r in self.results if r.name == name), None)

    def passed(self, name: str) -> bool:
        r = self.result(name)
        return bool(r and r.ok)

    @property
    def reachable(self) -> bool:
        return any(r.ok for r in self.results)

    def capabilities(self) -> ModelCapabilities:
        """Resolve probed capabilities (most reliable output mode wins)."""
        if self.passed("tool_output"):
            output = OutputMode.TOOL
        elif self.passed("native_output"):
            output = OutputMode.NATIVE
        else:
            output = OutputMode.PROMPTED
        if self.passed("exploration_tool"):
            tools = ToolSupport.RELIABLE
        elif self.passed("tool_output"):
            tools = ToolSupport.UNRELIABLE
        else:
            tools = ToolSupport.NONE
        return ModelCapabilities(
            tools=tools, structured_output=output, vision=self.passed("vision")
        )

    def recommendations(self) -> list[str]:
        recs: list[str] = []
        if not self.reachable:
            first = self.results[0] if self.results else None
            recs.append(
                "Endpoint unreachable or model unavailable"
                + (f": {first.error}" if first and first.error else "")
                + ". Check model name, base URL (no trailing /chat/completions) and API key."
            )
            return recs
        if not self.passed("tool_output"):
            recs.append(
                "Tool-based structured output failed; using "
                + ("'native'" if self.passed("native_output") else "'prompted'")
                + " output mode for this model."
            )
        if not self.passed("exploration_tool"):
            recs.append("Exploration tool calls unreliable; agents will use curated evidence instead of tools.")
        if not self.passed("vision"):
            recs.append("No vision support; screenshot-based checks will fall back to DOM-only analysis.")
        if not self.passed("prompted_output"):
            recs.append(
                "WARNING: prompted JSON output failed - this model may be too weak for healing duties."
            )
        return recs


#: probe that establishes whether an output mode can be produced at all.
MODE_PROBES: dict[OutputMode, str] = {
    OutputMode.TOOL: "tool_output",
    OutputMode.NATIVE: "native_output",
    OutputMode.PROMPTED: "prompted_output",
}

#: preference when the configured mode is broken and a fallback is needed.
_FALLBACK_ORDER = (OutputMode.TOOL, OutputMode.NATIVE, OutputMode.PROMPTED)


def safe_output_mode(working: dict[OutputMode, bool], preferred: OutputMode) -> OutputMode:
    """The preferred mode if the endpoint can produce it, else one that works.

    This is deliberately a *safety* rule, not a ranking rule. Probes establish
    whether a transport works, not whether it heals better: in the OpenRouter
    sweep `gemma-3-4b` passed both the native and prompted probes yet scored 75%
    prompted against 35% native, so a passing preference is never second-guessed.
    It is only overridden when it demonstrably cannot produce output at all --
    `qwen3-8b` fails the prompted probe and scored 0% (19 of 20 fixtures timed
    out) where native scored 95%.

    See `experiments/small-model-sweep/FINDINGS.md`.
    """
    if working.get(preferred, True):
        return preferred  # works, or was never probed -- leave the choice alone
    for mode in _FALLBACK_ORDER:
        if working.get(mode):
            return mode
    return preferred  # nothing works; the caller's choice is as good as any


async def probe_output_modes(
    model: Model | str, preferred: OutputMode, *, timeout: float | None = None
) -> dict[OutputMode, bool]:
    """Cheapest probe that can enforce the safety rule.

    Tests ``preferred`` first and stops there when it works -- one tiny call in
    the common case. Only a failure costs the extra probes needed to find a
    working fallback.
    """
    probe_fns = {
        OutputMode.TOOL: _probe_tool_output,
        OutputMode.NATIVE: _probe_native_output,
        OutputMode.PROMPTED: _probe_prompted_output,
    }
    if preferred not in probe_fns:
        return {}
    working: dict[OutputMode, bool] = {}

    async def check(mode: OutputMode) -> bool:
        coro = probe_fns[mode](model)
        if timeout is None:
            result = await _run_probe(MODE_PROBES[mode], coro)
        else:
            result = await asyncio.wait_for(_run_probe(MODE_PROBES[mode], coro), timeout=timeout)
        working[mode] = result.ok
        return result.ok

    try:
        if await check(preferred):
            return working
        for mode in _FALLBACK_ORDER:
            if mode is not preferred and await check(mode):
                break
    except Exception:
        # a probe that cannot even run must not break healing; an empty/partial
        # map leaves safe_output_mode with the configured choice
        pass
    return working


async def _run_probe(name: str, coro) -> ProbeResult:
    start = time.monotonic()
    try:
        await asyncio.wait_for(coro, timeout=PROBE_TIMEOUT_SECONDS)
        return ProbeResult(name=name, ok=True, latency_seconds=time.monotonic() - start)
    except Exception as exc:  # noqa: BLE001 - probes classify all failures
        return ProbeResult(
            name=name,
            ok=False,
            latency_seconds=time.monotonic() - start,
            error=f"{type(exc).__name__}: {exc}"[:300],
        )


_QUESTION = "Reply with answer='ok'."


async def _probe_tool_output(model: Model | str) -> None:
    agent = Agent(model, output_type=_Probe, retries=1)
    await agent.run(_QUESTION)


async def _probe_native_output(model: Model | str) -> None:
    agent = Agent(model, output_type=NativeOutput(_Probe), retries=1)
    await agent.run(_QUESTION)


async def _probe_prompted_output(model: Model | str) -> None:
    agent = Agent(model, output_type=PromptedOutput(_Probe), retries=1)
    await agent.run(_QUESTION)


async def _probe_exploration_tool(model: Model | str) -> None:
    calls: list[str] = []
    agent = Agent(
        model,
        output_type=_Probe,
        system_prompt="Always call the `lookup` tool before answering.",
        retries=1,
    )

    @agent.tool_plain
    def lookup(key: str) -> str:
        """Look up a value."""
        calls.append(key)
        return "the answer is 'ok'"

    await agent.run("Look up 'status' and reply with answer='ok'.")
    if not calls:
        raise RuntimeError("model never called the exploration tool")


async def _probe_vision(model: Model | str) -> None:
    agent = Agent(model, output_type=PromptedOutput(_Probe), retries=1)
    await agent.run(
        [
            "Describe this image in one word as answer.",
            BinaryContent(data=_TINY_PNG, media_type="image/png"),
        ]
    )


async def run_doctor(model: Model | str, *, model_name: str = "", include_vision: bool = True) -> DoctorReport:
    """Probe one model and return the report (probes run sequentially)."""
    name = model_name or (model if isinstance(model, str) else getattr(model, "model_name", str(model)))
    report = DoctorReport(model_name=str(name))
    probes = [
        ("tool_output", _probe_tool_output),
        ("native_output", _probe_native_output),
        ("prompted_output", _probe_prompted_output),
        ("exploration_tool", _probe_exploration_tool),
    ]
    for probe_name, fn in probes:
        report.results.append(await _run_probe(probe_name, fn(model)))
    if include_vision:
        report.results.append(await _run_probe("vision", _probe_vision(model)))
    return report
