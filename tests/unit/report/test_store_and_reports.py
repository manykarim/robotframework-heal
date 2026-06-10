import json

from heal.core.schemas import (
    BlastRadius,
    Confidence,
    Diagnosis,
    Evidence,
    EvidenceKind,
    FailureClass,
    FailureContext,
    FixProposal,
    HealEvent,
    HealOutcome,
    KeywordCall,
    ModelUsage,
    OutcomeStatus,
    RcaRecord,
)
from heal.report.history import HealHistory
from heal.report.html import render_dashboard
from heal.report.store import RunStore, load_events, merge_events
from heal.report.summary import build_summary, gha_annotations, write_summary


def make_event(event_id="e1", status=OutcomeStatus.HEALED, lineno=10, healed="css=#new", source="/s/login.robot"):
    return HealEvent(
        event_id=event_id,
        test_name="Login Test",
        suite_name="Login",
        source=source,
        lineno=lineno,
        keyword=KeywordCall(name="Click", args=["id=old"], owner_library="Browser", lineno=lineno, source=source),
        context=FailureContext(
            keyword=KeywordCall(name="Click", args=["id=old"], owner_library="Browser"),
            error_message="TimeoutError: waiting",
            failed_locator="id=old",
            evidence={
                EvidenceKind.DOM_EXCERPT.value: Evidence(kind=EvidenceKind.DOM_EXCERPT, excerpt="<body/>")
            },
        ),
        outcome=HealOutcome(
            status=status,
            diagnosis=Diagnosis(
                failure_class=FailureClass.LOCATOR_DRIFT, confidence=Confidence.HIGH, rationale="0 matches"
            ),
            healed_locator=healed if status is OutcomeStatus.HEALED else None,
            duration_seconds=12.3,
            usage=ModelUsage(model="MiniMax-M2.5", output_mode="prompted", requests=2, total_tokens=1234),
        ),
        rca=RcaRecord(
            failure_class=FailureClass.LOCATOR_DRIFT,
            clean_message="Button id changed from 'old' to 'new'.",
        ),
        fix_proposal=FixProposal(
            file=source, lineno=lineno, old_value="id=old", new_value=healed or "", blast_radius=BlastRadius.LOCAL
        )
        if status is OutcomeStatus.HEALED
        else None,
    )


def test_store_append_and_load(tmp_path):
    store = RunStore(tmp_path / "heal")
    store.append(make_event("e1"))
    store.append(make_event("e2", status=OutcomeStatus.UNHEALED, lineno=20))
    events = store.load()
    assert [e.event_id for e in events] == ["e1", "e2"]


def test_load_skips_corrupt_tail(tmp_path):
    store = RunStore(tmp_path)
    store.append(make_event("ok"))
    with store.path.open("a", encoding="utf-8") as f:
        f.write('{"event_id": "trunc')  # crash mid-write
    events = load_events(store.path)
    assert [e.event_id for e in events] == ["ok"]


def test_merge_dedupes_keeping_latest():
    first_run = [make_event("run1-a", status=OutcomeStatus.UNHEALED), make_event("run1-b", lineno=99)]
    rerun = [make_event("run2-a", status=OutcomeStatus.HEALED)]
    merged = merge_events(first_run, rerun)
    same_location = [e for e in merged if e.lineno == 10]
    assert len(same_location) == 1
    assert same_location[0].event_id == "run2-a"  # rerun wins
    assert len(merged) == 2


def test_summary_counts_and_write(tmp_path):
    events = [make_event("a"), make_event("b", status=OutcomeStatus.UNHEALED, lineno=20)]
    summary = write_summary(events, tmp_path / "summary.json")
    assert summary["transactions"] == 2
    assert summary["healed"] == 1 and summary["unhealed"] == 1
    assert summary["by_failure_class"] == {"locator-drift": 2}
    assert summary["total_tokens"] == 2468
    assert summary["fix_proposals"]["local"] == 1
    on_disk = json.loads((tmp_path / "summary.json").read_text())
    assert on_disk == summary


def test_gha_annotations_levels_and_location():
    healed, unhealed = make_event("a"), make_event("b", status=OutcomeStatus.UNHEALED, lineno=20)
    lines = gha_annotations([healed, unhealed])
    assert lines[0].startswith("::warning file=/s/login.robot,line=10::")
    assert lines[1].startswith("::error file=/s/login.robot,line=20::")


def test_dashboard_renders_self_contained(tmp_path):
    events = [make_event("a"), make_event("b", status=OutcomeStatus.UNHEALED, lineno=20)]
    out = render_dashboard(events, tmp_path / "heal_report.html")
    html = out.read_text(encoding="utf-8")
    assert "Login Test" in html
    assert "unhealed" in html and "healed" in html
    assert "fix proposal" in html
    assert "Button id changed" in html
    assert "<script src=" not in html and "href=" not in html  # self-contained


def test_history_hotspots(tmp_path):
    history = HealHistory(tmp_path / "history.sqlite")
    for i in range(4):
        history.record([make_event(f"e{i}")])
    history.record([make_event("other", status=OutcomeStatus.UNHEALED, lineno=20)])
    hotspots = history.hotspots(min_count=3, days=30)
    assert len(hotspots) == 1
    assert hotspots[0].failed_locator == "id=old"
    assert hotspots[0].heal_count == 4
    assert history.heal_count("/s/login.robot", "id=old") == 4
