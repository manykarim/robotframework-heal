"""Pure reference-generation logic (no mkdocs dependency, so it is unit-testable).

`gen_reference.py` is the thin mkdocs-gen-files hook that writes what these
functions return; tests import these functions directly.
"""

from __future__ import annotations

import enum
import inspect
import typing

import click
import typer

from heal.cli.main import app as cli_app
from heal.core.settings import HealSettings

ENV_PREFIX = "HEAL_"

GROUPS: list[tuple[str, str, list[str]]] = [
    ("Feature switches", "Master toggles and opt-in behaviours.",
     ["enabled", "locator_tiers", "heal_assertions", "form_fill", "fix_tier", "warm_start"]),
    ("Default model", "The model used for every agent role unless overridden below. "
     "Point `HEAL_BASE_URL` at any OpenAI-compatible endpoint or use a pydantic-ai provider "
     "string in `HEAL_MODEL` (e.g. `openai:gpt-4.1-mini`).",
     ["model", "base_url", "api_key", "output_mode"]),
    ("Per-role overrides", "Each agent role (`triage`, `locator`, `vision`, `rca`) can override "
     "the default model, endpoint, key and output mode. Unset values fall back to the defaults above — "
     "so `HEAL_MODEL` alone is enough for simple setups.",
     [f"{role}_{attr}" for role in ("triage", "locator", "vision", "rca")
      for attr in ("model", "base_url", "api_key", "output_mode")]),
    ("Budgets", "Caps that keep healing bounded in CI. Breaching the run cap degrades to RCA-only "
     "instead of failing the test run.",
     ["max_failure_seconds", "max_failure_tokens", "max_run_tokens", "request_limit", "agent_retries"]),
    ("Timing recovery", "", ["ready_timeout_seconds"]),
    ("Reporting", "Where artifacts and cross-run history are written.",
     ["report_dir", "history_db"]),
]


def _enum_type(annotation) -> type[enum.Enum] | None:
    for candidate in (annotation, *typing.get_args(annotation)):
        if isinstance(candidate, type) and issubclass(candidate, enum.Enum):
            return candidate
    return None


def _type_label(field) -> str:
    enum_t = _enum_type(field.annotation)
    if enum_t is not None:
        return " / ".join(f"`{e.value}`" for e in enum_t)
    args = [a for a in typing.get_args(field.annotation) if a is not type(None)]
    base = args[0] if args else field.annotation
    name = getattr(base, "__name__", str(base))
    return {"str": "string", "bool": "boolean", "int": "integer", "float": "number"}.get(name, name)


def _default_label(field) -> str:
    default = field.default
    if isinstance(default, enum.Enum):
        return f"`{default.value}`"
    if default is None or default == "":
        return "—"
    return f"`{default}`"


def _constraints(field) -> str:
    parts: list[str] = []
    for meta in field.metadata:
        for attr, sym in (("gt", ">"), ("ge", "≥"), ("lt", "<"), ("le", "≤")):
            if (value := getattr(meta, attr, None)) is not None:
                parts.append(f"{sym} {value}")
        if (pattern := getattr(meta, "pattern", None)) is not None:
            parts.append(f"matches `{pattern}`")
    return ", ".join(parts)


def env_var(field_name: str) -> str:
    return ENV_PREFIX + field_name.upper()


def _row(name: str, field) -> str:
    return (
        f"| `{env_var(name)}` | {_type_label(field)} | {_default_label(field)} "
        f"| {_constraints(field) or '—'} | {field.description or ''} |"
    )


def generate_config_reference() -> str:
    fields = HealSettings.model_fields
    undocumented = [n for n, f in fields.items() if not f.description]
    if undocumented:
        raise SystemExit(
            f"Config reference is incomplete — settings without a description: {undocumented}. "
            "Add a Field(description=...) in heal/core/settings.py."
        )

    lines = [
        "# Configuration reference", "",
        "All configuration is read from `HEAL_*` environment variables (the nearest `.env` "
        "is auto-loaded and overrides the process environment). This page is generated from "
        "the settings schema, so it always matches the installed version.", "",
    ]
    header = ["| Variable | Type | Default | Constraints | Description |", "|---|---|---|---|---|"]
    seen: set[str] = set()
    for title, blurb, names in GROUPS:
        lines += [f"## {title}", ""]
        if blurb:
            lines += [blurb, ""]
        lines += header
        for name in names:
            seen.add(name)
            lines.append(_row(name, fields[name]))
        lines.append("")

    leftover = [n for n in fields if n not in seen]
    if leftover:
        lines += ["## Other", ""] + header + [_row(n, fields[n]) for n in leftover] + [""]
    return "\n".join(lines)


def _format_param(param: click.Parameter) -> str:
    help_text = (getattr(param, "help", "") or "").replace("\n", " ")
    if isinstance(param, click.Argument):
        return f"| `{param.metavar or param.name.upper()}` | argument | {help_text} |"
    flags = ", ".join(f"`{o}`" for o in param.opts)
    default = ""
    if param.default not in (None, False) and not param.required:
        default = f" (default: `{param.default}`)"
    return f"| {flags} | option | {help_text}{default} |"


def generate_cli_reference() -> str:
    command = typer.main.get_command(cli_app)
    subcommands = command.commands
    rendered: set[str] = set()
    lines = [
        "# CLI reference", "",
        "The `heal` console script. This page is generated from the command app.", "",
        "```text", "heal [COMMAND] [ARGS]...", "```", "",
    ]
    for name in sorted(subcommands):
        cmd = subcommands[name]
        rendered.add(name)
        summary = (cmd.help or inspect.getdoc(cmd.callback) or "").split("\n\n")[0].replace("\n", " ")
        lines += [f"## `heal {name}`", "", summary, ""]
        params = [p for p in cmd.params if not (isinstance(p, click.Option) and p.name == "help")]
        if params:
            lines += ["| Parameter | Kind | Description |", "|---|---|---|"]
            lines += [_format_param(p) for p in params]
            lines.append("")

    expected = {(c.name or "").replace("_", "-") for c in cli_app.registered_commands}
    missed = {n for n in expected if n} - rendered
    if missed:
        raise SystemExit(f"CLI reference is incomplete — commands not rendered: {missed}.")
    return "\n".join(lines)
