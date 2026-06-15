"""Shared fix-artifact pipeline: one synthesis, several renderings.

Used by the listener at end-of-run and by `heal report` post-run: resolve
proposals -> synthesize healed contents -> healed copies + visual diffs
(always, read-only) and hand back everything tier-gated outputs need.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..core.schemas import HealEvent
from ..report.diff import DiffPage, FixMapping, write_diff_pages
from .apply import ApplyResult, synthesize_changes, write_healed_copies
from .resolve import ResolvedFix, resolve_fix


@dataclass
class FixArtifacts:
    proposals: list = field(default_factory=list)
    fixes: list[ResolvedFix] = field(default_factory=list)
    result: ApplyResult = field(default_factory=ApplyResult)
    pages: list[DiffPage] = field(default_factory=list)
    #: source file -> relative diff page path (for dashboard links)
    diff_links: dict[str, str] = field(default_factory=dict)
    #: "<file>|<old>|<new>" -> {link, target, inline} for the dashboard
    proposal_views: dict[str, dict] = field(default_factory=dict)

    @property
    def local_fixes(self) -> list[ResolvedFix]:
        return [f for f in self.fixes if f.blast_radius == "local"]


def build_fix_artifacts(events: list[HealEvent], directory: str | Path) -> FixArtifacts:
    """Synthesize healed copies + diff pages under `directory`. Read-only:
    original suites/resources are never modified here."""
    directory = Path(directory)
    artifacts = FixArtifacts()
    artifacts.proposals = [
        e.fix_proposal
        for e in events
        if e.fix_proposal and e.fix_proposal.kind in ("locator", "variable", "argument")
    ]
    if not artifacts.proposals:
        return artifacts
    artifacts.fixes = [
        resolve_fix(
            file=p.file, lineno=p.lineno,
            old_locator=p.old_value, new_locator=p.new_value,
        )
        for p in artifacts.proposals
    ]
    ordered = [f for f in artifacts.fixes if f.blast_radius == "local"] + [
        f for f in artifacts.fixes if f.blast_radius == "shared"
    ]
    artifacts.result = synthesize_changes(ordered)

    write_healed_copies(artifacts.result, directory / "healed_files")
    mappings: dict[str, list[FixMapping]] = {}
    for proposal, fix in zip(artifacts.proposals, artifacts.fixes):
        if fix.kind == "keyword-argument":
            targets = sorted({edit_file for edit_file, _, _, _ in fix.call_site_edits})
        elif fix.kind.startswith("variable") and fix.variable_file:
            targets = [fix.variable_file]
        else:
            targets = [fix.file]
        for target in targets:
            mappings.setdefault(target, []).append(
                FixMapping(proposal.old_value, proposal.new_value, fix.blast_radius)
            )
    artifacts.pages = write_diff_pages(artifacts.result.changes, directory / "diffs", mappings)
    artifacts.diff_links = {
        page.source: f"diffs/{page.path.name}" for page in artifacts.pages
    }

    # per-proposal dashboard views: diff-page link + inline changed lines
    from ..report.diff import inline_changed_rows

    changes_by_path = {c.path: c for c in artifacts.result.changes if c.changed}
    for proposal, fix in zip(artifacts.proposals, artifacts.fixes):
        if fix.kind == "keyword-argument" and fix.call_site_edits:
            target = fix.call_site_edits[0][0]
        elif fix.kind.startswith("variable") and fix.variable_file:
            target = fix.variable_file
        else:
            target = fix.file
        change = changes_by_path.get(target)
        if change is None:
            continue
        key = f"{proposal.file}|{proposal.old_value}|{proposal.new_value}"
        artifacts.proposal_views[key] = {
            "link": artifacts.diff_links.get(target, ""),
            "target": target,
            "inline": inline_changed_rows(change.original, change.healed),
        }
    return artifacts
