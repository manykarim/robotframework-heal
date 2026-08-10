from pathlib import Path

from heal.evals.corpus import (
    find_truth_conflicts,
    fixture_from_event,
    harvest,
    load_corpus,
    truth_scope,
    truths_conflict,
)
from heal.report.store import RunStore

from ..report.test_store_and_reports import make_event


def test_fixture_extraction_requires_resolvable_truth():
    healthy = make_event("e1", healed="css=#new")
    # the fixture DOM is "<body/>" -> #new does not resolve -> no fixture
    assert fixture_from_event(healthy) is None

    from heal.core.schemas import Evidence, EvidenceKind

    healthy.context.evidence[EvidenceKind.DOM_EXCERPT.value] = Evidence(
        kind=EvidenceKind.DOM_EXCERPT, excerpt="<body><button id='new'>x</button></body>"
    )
    fixture = fixture_from_event(healthy)
    assert fixture is not None
    assert fixture.truth_css == "#new"
    assert fixture.expected_class == "locator-drift"


def test_harvest_idempotent(tmp_path):
    from heal.core.schemas import Evidence, EvidenceKind

    event = make_event("e1", healed="css=#new")
    event.context.evidence[EvidenceKind.DOM_EXCERPT.value] = Evidence(
        kind=EvidenceKind.DOM_EXCERPT, excerpt="<body><button id='new'>x</button></body>"
    )
    store = RunStore(tmp_path / "run1" / "heal")
    store.append(event)

    out = tmp_path / "fixtures"
    added, skipped = harvest([tmp_path], out)
    assert (added, skipped) == (1, 0)
    added, skipped = harvest([tmp_path], out)
    assert (added, skipped) == (0, 1)

    corpus = load_corpus(out)
    assert len(corpus) == 1
    _, fixture = corpus[0]
    assert fixture.context.failed_locator == "id=old"
    assert fixture.truth_css == "#new"


PAGE = "<body><input id='firstname'/><input id='surname'/></body>"
NESTED = "<body><button type='submit'><i class='fa-sign-in'>go</i></button></body>"


def _fixture(healed: str, dom: str, *, suite: str = "Atest.Ait Llm", event_id: str = "e1"):
    from heal.core.schemas import Evidence, EvidenceKind

    event = make_event(event_id, healed=healed)
    event.context.evidence[EvidenceKind.DOM_EXCERPT.value] = Evidence(
        kind=EvidenceKind.DOM_EXCERPT, excerpt=dom
    )
    event.context.suite_name = suite
    return event


def test_conflicting_ground_truth_is_detected_and_not_harvested(tmp_path):
    """A wrong-but-verified heal must not become an unwinnable fixture.

    Ground truth is harvested from heals this engine performed, so a heal that
    verified against the wrong element would otherwise be graded as truth --
    silently capping corpus accuracy below 100%.
    """
    good = _fixture("css=#surname", PAGE, event_id="e1")
    wrong = _fixture("css=#firstname", PAGE, event_id="e2")  # same action, other element

    store = RunStore(tmp_path / "run1" / "heal")
    store.append(good)
    store.append(wrong)

    out = tmp_path / "fixtures"
    added, skipped = harvest([tmp_path], out)
    assert (added, skipped) == (1, 1)  # the contradicting one is rejected
    corpus = load_corpus(out)
    assert [f.truth_css for _, f in corpus] == ["#surname"]
    assert find_truth_conflicts(corpus) == []


def test_nested_target_is_not_a_conflict(tmp_path):
    # clicking button > i clicks the button: different node, same target
    outer = _fixture("css=button[type='submit']", NESTED, event_id="e1")
    inner = _fixture("css=button[type='submit'] i.fa-sign-in", NESTED, event_id="e2")

    store = RunStore(tmp_path / "run1" / "heal")
    store.append(outer)
    store.append(inner)

    added, skipped = harvest([tmp_path], tmp_path / "fixtures")
    assert (added, skipped) == (2, 0)


def test_scope_ignores_run_root_in_suite_name():
    # the same suite recorded under different roots must share a truth scope
    a = fixture_from_event(_fixture("css=#surname", PAGE, suite="Atest.Ait Llm"))
    b = fixture_from_event(
        _fixture("css=#firstname", PAGE, suite="Robotframework-Heal.Tests.Atest.Ait Llm")
    )
    assert a is not None and b is not None
    assert truth_scope(a) == truth_scope(b)
    assert truths_conflict(a, b)


def test_shipped_corpus_has_no_conflicting_ground_truth():
    corpus = load_corpus(Path(__file__).parents[2] / "evals" / "fixtures")
    assert corpus, "corpus fixtures not found"
    conflicts = [(a.name, b.name) for a, b in find_truth_conflicts(corpus)]
    assert conflicts == []
