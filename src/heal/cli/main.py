"""heal CLI: triage, report, apply, doctor, mcp."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from ..core.settings import ROLES, HealSettings
from ..report.store import EVENTS_FILENAME, load_events

app = typer.Typer(help="Failure triage, self-healing and RCA for Robot Framework runs.")


def _events_path(target: Path) -> Path:
    if target.is_file():
        return target
    for candidate in (target / EVENTS_FILENAME, target / "heal" / EVENTS_FILENAME):
        if candidate.is_file():
            return candidate
    raise typer.BadParameter(f"no {EVENTS_FILENAME} found under {target}")


def _redact(value: str | None) -> str:
    if not value:
        return "(unset)"
    return value[:4] + "…" if len(value) > 4 else "…"


def _print_config(settings: HealSettings) -> None:
    typer.echo("resolved configuration:")
    for role in ROLES:
        cfg = settings.role_config(role)
        typer.echo(
            f"  {role:8} model={cfg.model or '(unset)'} base_url={cfg.base_url or '(default provider)'} "
            f"api_key={_redact(cfg.api_key)} output_mode={cfg.output_mode.value}"
        )
    typer.echo(
        f"  budgets  max_failure_seconds={settings.max_failure_seconds} "
        f"max_run_tokens={settings.max_run_tokens} fix_tier={settings.fix_tier.value}"
    )


@app.command()
def triage(target: Path = typer.Argument(..., help="RF output dir or events.jsonl")):
    """Summarize recorded failures: diagnoses, heals, RCAs, fix proposals."""
    events = load_events(_events_path(target))
    if not events:
        typer.echo("no heal events recorded")
        raise typer.Exit(0)
    from ..report.summary import build_summary

    summary = build_summary(events)
    typer.echo(
        f"{summary['transactions']} transactions: {summary['healed']} healed, "
        f"{summary['unhealed']} unhealed, {summary['suppressed']} suppressed "
        f"({summary['total_tokens']} tokens)"
    )
    for event in events:
        if not event.outcome:
            continue
        status = event.outcome.status.value
        line = f"[{status:9}] {event.test_name} :: {event.keyword.name if event.keyword else '?'}"
        if event.source:
            line += f"  ({Path(event.source).name}:{event.lineno})"
        typer.echo(line)
        if event.rca:
            typer.echo(f"            {event.rca.clean_message}")
        if event.fix_proposal:
            fp = event.fix_proposal
            typer.echo(
                f"            fix[{fp.blast_radius.value}]: {fp.old_value!r} -> {fp.new_value!r}"
            )


@app.command()
def report(
    target: Path = typer.Argument(..., help="RF output dir or events.jsonl"),
    out: Path = typer.Option(None, help="Output directory (default: alongside the store)"),
):
    """Render the HTML dashboard and summary.json from a run store."""
    events_path = _events_path(target)
    events = load_events(events_path)
    out_dir = out or events_path.parent
    from ..report.html import render_dashboard
    from ..report.summary import write_summary

    dashboard = render_dashboard(events, out_dir / "heal_report.html")
    write_summary(events, out_dir / "summary.json")
    typer.echo(f"report written to {dashboard}")


@app.command()
def apply(
    target: Path = typer.Argument(..., help="RF output dir or events.jsonl"),
    in_place: bool = typer.Option(False, "--in-place", help="Apply fixes to source files (clean git tree required)"),
    force: bool = typer.Option(False, help="Apply in place even on a dirty git tree"),
    patch_out: Path = typer.Option(None, "--patch", help="Write the unified patch to this file"),
):
    """Apply recorded fix proposals (patch by default; --in-place opt-in)."""
    events = load_events(_events_path(target))
    proposals = [e.fix_proposal for e in events if e.fix_proposal]
    if not proposals:
        typer.echo("no fix proposals recorded")
        raise typer.Exit(0)
    from ..fix.apply import apply_in_place, synthesize_changes, unified_patch
    from ..fix.resolve import resolve_fix

    fixes = [
        resolve_fix(file=p.file, lineno=p.lineno, old_locator=p.old_value, new_locator=p.new_value)
        for p in proposals
    ]
    local = [f for f in fixes if f.blast_radius == "local"]
    shared = [f for f in fixes if f.blast_radius == "shared"]
    if in_place:
        result = synthesize_changes(local)
        written, refused = apply_in_place(result, force=force)
        for path in written:
            typer.echo(f"applied: {path}")
        for path in refused:
            typer.echo(f"REFUSED (dirty git tree, use --force or commit first): {path}")
        if shared:
            typer.echo(f"{len(shared)} shared-blast-radius fix(es) NOT applied in place:")
            for fix in shared:
                typer.echo(f"  ${{{fix.variable_name}}} used at {len(fix.usages)} sites — review the patch")
        if refused and not force:
            raise typer.Exit(1)
    result = synthesize_changes(local + shared)
    patch = unified_patch(result)
    if patch:
        out = patch_out or (_events_path(target).parent / "heal.patch")
        out.write_text(patch, encoding="utf-8")
        typer.echo(f"patch written to {out} (git apply {out})")


@app.command()
def doctor(
    role: str = typer.Option("locator", help=f"Agent role to probe ({', '.join(ROLES)} or 'all')"),
    vision: bool = typer.Option(False, help="Include the vision probe"),
):
    """Probe the configured model endpoints and resolve capabilities."""
    from ..core.doctor import run_doctor
    from ..core.runtime import AgentRuntime

    settings = HealSettings()
    _print_config(settings)
    runtime = AgentRuntime(settings)
    roles = list(ROLES) if role == "all" else [role]
    failed = False
    for r in roles:
        cfg = settings.role_config(r)
        if not cfg.model:
            typer.echo(f"\n{r}: no model configured (set HEAL_MODEL or HEAL_{r.upper()}_MODEL)")
            failed = True
            continue
        typer.echo(f"\nprobing {r} -> {cfg.model} ...")
        report = asyncio.run(run_doctor(runtime.model(r), model_name=cfg.model, include_vision=vision))
        for res in report.results:
            typer.echo(f"  {res.name:18} {'PASS' if res.ok else 'FAIL':4} {res.latency_seconds:5.1f}s  {res.error[:70]}")
        caps = report.capabilities()
        typer.echo(f"  resolved: output={caps.structured_output.value} tools={caps.tools.value} vision={caps.vision}")
        for rec in report.recommendations():
            typer.echo(f"  - {rec}")
        failed = failed or not report.reachable
    raise typer.Exit(1 if failed else 0)


@app.command()
def mcp(
    target: Path = typer.Argument(None, help="RF output dir or events.jsonl to expose (optional)"),
):
    """Start the MCP server (stdio) over the run store and fix engine."""
    from ..mcp.server import serve

    serve(events_path=_events_path(target) if target else None)


@app.command()
def corpus(
    paths: list[Path] = typer.Argument(..., help="Run stores or directories containing events.jsonl"),
    out: Path = typer.Option(Path("tests/evals/fixtures"), help="Fixture output directory"),
):
    """Harvest ground-truth eval fixtures from recorded healing runs."""
    from ..evals.corpus import harvest

    added, skipped = harvest([str(p) for p in paths], out)
    typer.echo(f"harvested {added} new fixture(s), {skipped} already present, into {out}")


@app.command()
def history(
    db: Path = typer.Argument(..., help="Path to history.sqlite"),
    min_count: int = typer.Option(3),
    days: int = typer.Option(30),
):
    """Show maintenance hotspots (locators healed repeatedly)."""
    from ..report.history import HealHistory

    for hotspot in HealHistory(db).hotspots(min_count=min_count, days=days):
        typer.echo(
            f"{hotspot.heal_count:3}x {hotspot.failed_locator}  ({hotspot.source}, last {hotspot.last_healed_at})"
        )


if __name__ == "__main__":
    app()
