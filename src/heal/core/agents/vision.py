"""Vision agent: screenshot Q&A with strict bool schemas (probe 5 lesson).

Enabled only when a vision model is explicitly configured
(`HEAL_VISION_MODEL`); every failure degrades to None so callers fall back
to DOM-only analysis.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import BinaryContent
from pydantic_ai.usage import UsageLimits

from ..runtime import AgentRuntime

ROLE = "vision"


class LoadingVerdict(BaseModel):
    is_loading: bool
    reason: str = ""


class FormVerdict(BaseModel):
    has_validation_error: bool
    error_fields: list[str] = []
    reason: str = ""


class AssertionVerdict(BaseModel):
    drift_confirmed: bool
    actual_on_screen: str = ""
    semantic_change: bool = False
    reason: str = ""


def vision_available(runtime: AgentRuntime) -> bool:
    return bool(runtime.settings.vision_model)


async def ask_vision(
    runtime: AgentRuntime,
    schema: type[BaseModel],
    question: str,
    screenshot_png: bytes,
    usage_limits: UsageLimits | None = None,
):
    """Returns the validated verdict, or None when unavailable/failed."""
    if not vision_available(runtime):
        return None
    agent = runtime.build_agent(ROLE, schema, system_prompt="You analyze UI screenshots for test automation.")
    try:
        result = await agent.run(
            [question, BinaryContent(data=screenshot_png, media_type="image/png")],
            usage_limits=usage_limits,
        )
    except Exception:
        return None
    return result.output
