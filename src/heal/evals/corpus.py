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


def find_stores(paths: list[str | Path]) -> list[Path]:
    stores: list[Path] = []
    for path in map(Path, paths):
        if path.is_file():
            stores.append(path)
        elif path.is_dir():
            stores.extend(sorted(path.rglob("events.jsonl")))
    return stores


def harvest(paths: list[str | Path], out_dir: str | Path) -> tuple[int, int]:
    """Extract fixtures from run stores into out_dir. Returns (added, skipped)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = {
        p.name[: -len(FIXTURE_SUFFIX)].split("-")[-1]
        for p in out_dir.glob(f"*{FIXTURE_SUFFIX}")
    }
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
            existing.add(key)
            suite = (fixture.context.suite_name or "case").split(".")[-1].lower().replace(" ", "-")
            (out_dir / f"{suite}-{key}{FIXTURE_SUFFIX}").write_text(fixture.dump(), encoding="utf-8")
            added += 1
    return added, skipped


def load_corpus(fixture_dir: str | Path) -> list[tuple[Path, Fixture]]:
    fixture_dir = Path(fixture_dir)
    return [
        (path, Fixture.load(path))
        for path in sorted(fixture_dir.glob(f"*{FIXTURE_SUFFIX}"))
    ]
