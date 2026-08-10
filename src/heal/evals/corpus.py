"""Ground-truth corpus harvesting: recorded heals become replay-eval fixtures.

A fixture is a healed event whose verified locator resolves to exactly one
element in the recorded DOM evidence — that element is the ground truth any
tier/model/prompt change must still find. Deduplicated by (failed locator,
healed locator, DOM hash) so re-harvesting the same runs is a no-op.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from ..core.schemas import EvidenceKind, FailureContext, HealEvent, OutcomeStatus
from ..report.store import load_events

FIXTURE_SUFFIX = ".fixture.json"


@dataclass
class Fixture:
    context: FailureContext
    truth_css: str
    expected_class: str
    source_event: str = ""

    def dump(self) -> str:
        return json.dumps(
            {
                "context": json.loads(self.context.model_dump_json(exclude_none=True)),
                "truth_css": self.truth_css,
                "expected_class": self.expected_class,
                "source_event": self.source_event,
            },
            indent=1,
        )

    @classmethod
    def load(cls, path: str | Path) -> "Fixture":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            context=FailureContext.model_validate(payload["context"]),
            truth_css=payload["truth_css"],
            expected_class=payload.get("expected_class", "locator-drift"),
            source_event=payload.get("source_event", ""),
        )


def normalize_to_css(locator: str) -> str | None:
    """healed locator -> plain CSS resolvable by bs4, or None (e.g. xpath)."""
    css = locator
    if css.startswith("css="):
        css = css[4:]
    elif css.startswith("id="):
        css = "#" + css[3:]
    elif css.startswith(("xpath=", "//")) or ">>>" in css:
        return None
    return css.replace(":visible", "").replace(" >> nth=0", "").strip() or None


def fixture_from_event(event: HealEvent) -> Fixture | None:
    if not (event.outcome and event.outcome.status is OutcomeStatus.HEALED):
        return None
    if not (event.outcome.healed_locator and event.context):
        return None
    dom = event.context.evidence_of(EvidenceKind.DOM_EXCERPT)
    if dom is None or not dom.excerpt:
        return None
    css = normalize_to_css(event.outcome.healed_locator)
    if css is None:
        return None
    try:
        matches = BeautifulSoup(dom.excerpt, "html.parser").select(css)
    except Exception:
        return None
    if len(matches) != 1:
        return None
    return Fixture(
        context=event.context,
        truth_css=css,
        expected_class=event.outcome.diagnosis.failure_class.value,
        source_event=f"{event.suite_name}::{event.test_name}::{event.event_id}",
    )


def _fixture_key(fixture: Fixture) -> str:
    dom = fixture.context.evidence_of(EvidenceKind.DOM_EXCERPT)
    raw = "|".join(
        [
            fixture.context.failed_locator or "",
            fixture.truth_css,
            hashlib.sha1((dom.excerpt if dom else "").encode()).hexdigest(),
        ]
    )
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _suite_slug(suite_name: str | None) -> str:
    """Leaf suite name — the same normalisation harvest uses for filenames.

    The full dotted name carries the run root ("Robotframework-Heal.Tests.Atest.Ait Llm"
    vs "Atest.Ait Llm"), so only the leaf is stable across recordings.
    """
    return (suite_name or "case").split(".")[-1].lower().replace(" ", "-")


def truth_scope(fixture: Fixture) -> tuple[str, str, tuple[str, ...], str]:
    """The action a fixture grades. Two fixtures sharing a scope must agree."""
    kw = fixture.context.keyword
    return (
        _suite_slug(fixture.context.suite_name),
        kw.name,
        tuple(kw.args or []),
        fixture.context.failed_locator or "",
    )


def _soup(fixture: Fixture) -> BeautifulSoup | None:
    dom = fixture.context.evidence_of(EvidenceKind.DOM_EXCERPT)
    if dom is None or not dom.excerpt:
        return None
    try:
        return BeautifulSoup(dom.excerpt, "html.parser")
    except Exception:
        return None


def truths_conflict(a: Fixture, b: Fixture) -> bool:
    """Do two same-scope fixtures name incompatible ground-truth elements?

    Grading is element identity, so two fixtures for the same action must not
    point at different elements — otherwise one of them is unwinnable and the
    accuracy ceiling silently drops below 100%. Selector *form* is irrelevant
    (``#firstname`` and ``input#firstname`` are the same node), and a nested
    target is not a conflict either: clicking ``button > i`` clicks the button.
    """
    for fixture in (a, b):
        soup = _soup(fixture)
        if soup is None:
            continue
        try:
            hits_a, hits_b = soup.select(a.truth_css), soup.select(b.truth_css)
        except Exception:
            continue
        if len(hits_a) != 1 or len(hits_b) != 1:
            continue
        x, y = hits_a[0], hits_b[0]
        if x is y or y in x.parents or x in y.parents:
            return False  # same node, or one contains the other
    return True


def find_truth_conflicts(corpus: list[tuple[Path, Fixture]]) -> list[tuple[Path, Path]]:
    """Pairs of fixtures that grade the same action against different elements."""
    by_scope: dict[tuple, list[tuple[Path, Fixture]]] = {}
    for path, fixture in corpus:
        by_scope.setdefault(truth_scope(fixture), []).append((path, fixture))
    conflicts: list[tuple[Path, Path]] = []
    for entries in by_scope.values():
        for i, (path_a, fix_a) in enumerate(entries):
            for path_b, fix_b in entries[i + 1 :]:
                if truths_conflict(fix_a, fix_b):
                    conflicts.append((path_a, path_b))
    return conflicts


def find_stores(paths: list[str | Path]) -> list[Path]:
    stores: list[Path] = []
    for path in map(Path, paths):
        if path.is_file():
            stores.append(path)
        elif path.is_dir():
            stores.extend(sorted(path.rglob("events.jsonl")))
    return stores


def harvest(paths: list[str | Path], out_dir: str | Path) -> tuple[int, int]:
    """Extract fixtures from run stores into out_dir. Returns (added, skipped).

    A candidate that contradicts an already-harvested fixture for the same
    action is skipped: ground truth comes from heals this engine performed, so
    one wrong-but-verified heal would otherwise become an unwinnable fixture.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = {
        p.name[: -len(FIXTURE_SUFFIX)].split("-")[-1]
        for p in out_dir.glob(f"*{FIXTURE_SUFFIX}")
    }
    by_scope: dict[tuple, list[Fixture]] = {}
    for _path, known in load_corpus(out_dir):
        by_scope.setdefault(truth_scope(known), []).append(known)
    added = skipped = 0
    for store in find_stores(paths):
        for event in load_events(store):
            fixture = fixture_from_event(event)
            if fixture is None:
                continue
            key = _fixture_key(fixture)
            if key in existing:
                skipped += 1
                continue
            scope = truth_scope(fixture)
            if any(truths_conflict(fixture, known) for known in by_scope.get(scope, ())):
                skipped += 1
                continue
            existing.add(key)
            by_scope.setdefault(scope, []).append(fixture)
            suite = _suite_slug(fixture.context.suite_name)
            (out_dir / f"{suite}-{key}{FIXTURE_SUFFIX}").write_text(fixture.dump(), encoding="utf-8")
            added += 1
    return added, skipped


def load_corpus(fixture_dir: str | Path) -> list[tuple[Path, Fixture]]:
    fixture_dir = Path(fixture_dir)
    return [
        (path, Fixture.load(path))
        for path in sorted(fixture_dir.glob(f"*{FIXTURE_SUFFIX}"))
    ]
