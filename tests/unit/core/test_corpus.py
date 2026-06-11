from heal.evals.corpus import fixture_from_event, harvest, load_corpus
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
