"""Typed configuration for the healing engine (env-driven, HEAL_ prefix).

Per-role model settings resolve with fallback to the default model config,
so a single `HEAL_MODEL` is enough for simple setups while every agent role
(triage / locator / vision / rca) can point at its own backend.
"""

from __future__ import annotations

import warnings
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROLES = ("triage", "locator", "vision", "rca")


class OutputMode(str, Enum):
    AUTO = "auto"
    TOOL = "tool"
    NATIVE = "native"
    PROMPTED = "prompted"


class FixTier(str, Enum):
    REPORT = "report"
    PATCH = "patch"
    IN_PLACE = "in-place"


class ResolvedModelConfig(BaseModel):
    """Effective model configuration for one agent role after fallback."""

    role: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    output_mode: OutputMode = OutputMode.AUTO


class HealSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HEAL_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- feature switches ---
    enabled: bool = Field(True, description="Master switch for the healing engine.")
    heal_assertions: bool = Field(False, description="Enable assertion-drift healing (opt-in).")
    form_fill: bool = Field(False, description="Allow form-diagnosis to fill fields (opt-in; diagnose-only by default).")
    fix_tier: FixTier = Field(FixTier.REPORT, description="Highest fix-application tier allowed.")

    # --- default model (fallback for all roles) ---
    model: str = Field("", description="Default model name (e.g. 'MiniMax-M2.5' or 'openai:gpt-4.1-mini').")
    base_url: str | None = Field(None, description="Default OpenAI-compatible endpoint base URL.")
    api_key: str | None = Field(None, description="Default API key for the endpoint.")
    output_mode: OutputMode = Field(OutputMode.AUTO, description="Default structured-output mode.")

    # --- per-role overrides (fall back to the defaults above) ---
    triage_model: str | None = None
    triage_base_url: str | None = None
    triage_api_key: str | None = None
    triage_output_mode: OutputMode | None = None

    locator_model: str | None = None
    locator_base_url: str | None = None
    locator_api_key: str | None = None
    locator_output_mode: OutputMode | None = None

    vision_model: str | None = None
    vision_base_url: str | None = None
    vision_api_key: str | None = None
    vision_output_mode: OutputMode | None = None

    rca_model: str | None = None
    rca_base_url: str | None = None
    rca_api_key: str | None = None
    rca_output_mode: OutputMode | None = None

    # --- budgets ---
    max_failure_seconds: float = Field(60.0, gt=0, description="Wall-clock cap per healing transaction.")
    max_failure_tokens: int = Field(50_000, gt=0, description="Token cap per healing transaction.")
    max_run_tokens: int = Field(2_000_000, gt=0, description="Token cap per test run; breach degrades to RCA-only.")
    request_limit: int = Field(8, gt=0, description="Max LLM requests per agent run within one transaction.")
    agent_retries: int = Field(3, ge=0, description="Output-validator retries per agent run.")

    # --- timing recovery ---
    ready_timeout_seconds: float = Field(20.0, gt=0, description="Max wait for page-ready in timing recovery.")

    # --- reporting ---
    report_dir: str | None = Field(None, description="Report directory; defaults to <RF output dir>/heal.")
    history_db: str | None = Field(None, description="Path to the cross-run healing history SQLite db.")

    def role_config(self, role: str) -> ResolvedModelConfig:
        """Resolve the effective model configuration for an agent role."""
        if role not in ROLES:
            raise ValueError(f"Unknown agent role {role!r}; expected one of {ROLES}")
        return ResolvedModelConfig(
            role=role,
            model=getattr(self, f"{role}_model") or self.model,
            base_url=getattr(self, f"{role}_base_url") or self.base_url,
            api_key=getattr(self, f"{role}_api_key") or self.api_key,
            output_mode=getattr(self, f"{role}_output_mode") or self.output_mode,
        )


#: Legacy `SelfHealing` listener kwargs -> (settings field, value mapper) or None when dropped.
_LEGACY_KWARG_MAP: dict[str, tuple[str, Any] | None] = {
    "fix": None,  # realtime vs retry: realtime is the only supported mode for now
    "heal_assertions": ("heal_assertions", bool),
    "use_llm_for_locator_proposals": None,  # proposal strategy now resolved per model capability
    "collect_locator_info": None,  # superseded by the run store
    "use_locator_db": None,  # superseded by the healing history db
    "locator_db_file": ("history_db", str),
}


def settings_from_legacy_kwargs(_warn: bool = True, **kwargs: Any) -> HealSettings:
    """Build settings from legacy `SelfHealing(...)` keyword arguments.

    Unknown kwargs raise TypeError; known-but-dropped kwargs emit a
    DeprecationWarning and are ignored.
    """
    overrides: dict[str, Any] = {}
    for name, value in kwargs.items():
        if name not in _LEGACY_KWARG_MAP:
            raise TypeError(f"SelfHealing got an unexpected keyword argument {name!r}")
        mapping = _LEGACY_KWARG_MAP[name]
        if mapping is None:
            if _warn:
                warnings.warn(
                    f"SelfHealing argument {name!r} is deprecated and has no effect; "
                    "see the HEAL_* configuration reference.",
                    DeprecationWarning,
                    stacklevel=3,
                )
            continue
        field, caster = mapping
        if _warn:
            warnings.warn(
                f"SelfHealing argument {name!r} is deprecated; set HEAL_{field.upper()} instead.",
                DeprecationWarning,
                stacklevel=3,
            )
        overrides[field] = caster(value)
    return HealSettings(**overrides)
