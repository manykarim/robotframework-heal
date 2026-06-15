"""MCP server over the heal run store and fix engine (stdio transport).

Decision (task 8.2): the official `mcp` SDK's FastMCP is used rather than
pydantic-ai's MCP server support — we expose *data* (failure bundles, fix
proposals) and *actions* (apply_fix with tier enforcement), not agents;
FastMCP gives tools + resources directly.

A coding agent (e.g. Claude Code) drives the triage->inspect->fix workflow:
list failures, read one bundle with full evidence, then apply fixes — where
`shared` blast radius is never applied in place; the agent receives the patch
plus the usage list and makes the judgment call itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..core.schemas import HealEvent
from ..report.store import load_events

_server = FastMCP("heal")
_events_path: Path | None = None


def _events() -> list[HealEvent]:
    if _events_path is None or not _events_path.is_file():
        return []
    return load_events(_events_path)


@_server.tool()
def list_failures() -> str:
    """List recorded healing transactions: id, test, status, failure class."""
    rows = [
        {
            "event_id": e.event_id,
            "test": e.test_name,
            "keyword": e.keyword.name if e.keyword else None,
            "status": e.outcome.status.value if e.outcome else None,
            "failure_class": e.outcome.diagnosis.failure_class.value if e.outcome else None,
            "source": e.source,
            "lineno": e.lineno,
            "has_fix_proposal": e.fix_proposal is not None,
        }
        for e in _events()
    ]
    return json.dumps(rows, indent=1)


@_server.tool()
def get_failure_bundle(event_id: str) -> str:
    """Full bundle for one transaction: diagnosis, RCA, evidence, attempts, fix proposal."""
    for event in _events():
        if event.event_id == event_id:
            return event.model_dump_json(indent=1, exclude_none=True)
    return json.dumps({"error": f"no event {event_id!r}"})


@_server.tool()
def get_fix_proposals() -> str:
    """All fix proposals with resolved blast radius and usage sites."""
    rows = [
        e.fix_proposal.model_dump(mode="json")
        | {"event_id": e.event_id, "test": e.test_name}
        for e in _events()
        if e.fix_proposal
    ]
    return json.dumps(rows, indent=1)


@_server.tool()
def apply_fix(event_id: str, in_place: bool = False, force: bool = False) -> str:
    """Apply one fix proposal. `shared` blast radius is never applied in place —
    the patch and usage list are returned for the caller to act on."""
    from ..fix.apply import apply_in_place, synthesize_changes, unified_patch
    from ..fix.resolve import resolve_fix

    event = next((e for e in _events() if e.event_id == event_id), None)
    if event is None or event.fix_proposal is None:
        return json.dumps({"error": f"no fix proposal for {event_id!r}"})
    p = event.fix_proposal
    fix = resolve_fix(file=p.file, lineno=p.lineno, old_locator=p.old_value, new_locator=p.new_value)
    if fix.kind == "unresolved":
        return json.dumps({"error": "fix origin could not be resolved against the current source"})
    result = synthesize_changes([fix])
    patch = unified_patch(result)
    if in_place and fix.blast_radius == "shared":
        return json.dumps(
            {
                "refused": "shared blast radius is never applied in place",
                "usages": fix.usages,
                "patch": patch,
            }
        )
    if in_place:
        written, refused = apply_in_place(result, force=force)
        return json.dumps({"written": written, "refused_dirty_tree": refused, "patch": patch})
    return json.dumps({"patch": patch, "blast_radius": fix.blast_radius, "usages": fix.usages})


@_server.tool()
def healing_history(db_path: str, min_count: int = 3, days: int = 30) -> str:
    """Maintenance hotspots: locators healed repeatedly across runs."""
    from ..report.history import HealHistory

    hotspots = HealHistory(db_path).hotspots(min_count=min_count, days=days)
    return json.dumps([h.__dict__ for h in hotspots], indent=1)


@_server.resource("heal://events")
def events_resource() -> str:
    """The raw run store (JSONL)."""
    return _events_path.read_text(encoding="utf-8") if _events_path and _events_path.is_file() else ""


def serve(events_path: Path | None = None) -> None:
    global _events_path
    _events_path = events_path
    _server.run()
