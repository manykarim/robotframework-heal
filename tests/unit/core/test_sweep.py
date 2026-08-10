"""Sweep harness: sampling, grading and aggregation (all offline, no backend)."""

import os
from pathlib import Path

from heal.core.schemas import Evidence, EvidenceKind, FailureContext, KeywordCall
from heal.evals.corpus import Fixture
from heal.evals.sweep import (
    grade,
    isolated_env,
    stratified_sample,
    summarize,
)

PAGE = "<body><input id='firstname'/><input id='surname'/><button id='go'>go</button></body>"


def _fixture(suite: str, keyword: str = "Fill Text", args=("id=last_name", "smith"), truth="#surname"):
    ctx = FailureContext(
        keyword=KeywordCall(name=keyword, args=list(args), owner_library="Browser", lineno=1, source="/s.robot"),
        error_message="TimeoutError",
        test_name="T",
        suite_name=suite,
        failed_locator=args[0],
        evidence={
            EvidenceKind.DOM_EXCERPT.value: Evidence(kind=EvidenceKind.DOM_EXCERPT, excerpt=PAGE)
        },
    )
    return Fixture(context=ctx, truth_css=truth, expected_class="locator-drift")


def _entry(name: str, fixture: Fixture) -> tuple[Path, Fixture]:
    return Path(f"{name}.fixture.json"), fixture


def test_stratified_sample_spreads_across_suites():
    # 4 from one suite, 1 each from two others -- taking the first 3 in order
    # would draw only from suite-a (the defect this replaces)
    corpus = [
        _entry(f"suite-a-{i:04x}", _fixture("A", args=(f"id=f{i}", "v"))) for i in range(4)
    ]
    corpus += [_entry("suite-b-0001", _fixture("B", args=("id=b", "v")))]
    corpus += [_entry("suite-c-0001", _fixture("C", args=("id=c", "v")))]

    picked = stratified_sample(corpus, 3)
    suites = {p.name.rsplit("-", 1)[0] for p, _ in picked}
    assert suites == {"suite-a", "suite-b", "suite-c"}


def test_stratified_sample_drops_duplicate_actions():
    # the same keyword+args+locator recorded three times is one scenario
    corpus = [_entry(f"suite-a-{i:04x}", _fixture("A")) for i in range(3)]
    corpus += [_entry("suite-a-ffff", _fixture("A", args=("id=other", "v")))]

    picked = stratified_sample(corpus, 0)  # 0 == whole deduplicated corpus
    assert len(picked) == 2


def test_stratified_sample_exhausts_smaller_suites_without_stalling():
    corpus = [_entry(f"suite-a-{i:04x}", _fixture("A", args=(f"id=f{i}", "v"))) for i in range(5)]
    corpus += [_entry("suite-b-0001", _fixture("B", args=("id=b", "v")))]

    picked = stratified_sample(corpus, 4)
    assert len(picked) == 4  # suite-b runs dry, suite-a fills the rest


def test_grade_rejects_unique_but_wrong_element():
    """The failure verification cannot catch: valid, unique, visible -- and wrong."""
    fixture = _fixture("A", truth="#surname")
    assert grade(fixture, "css=#surname") is True
    assert grade(fixture, "css=input#surname") is True  # selector form is irrelevant
    assert grade(fixture, "css=#firstname") is False  # the corpus-poisoning case
    assert grade(fixture, None) is False


def test_grade_rejects_ambiguous_locator():
    fixture = _fixture("A", truth="#surname")
    assert grade(fixture, "css=input") is False  # matches two nodes


def test_summarize_keeps_rca_out_of_headline_latency():
    # healed fixtures never trigger RCA; unhealed ones pay an extra round-trip
    results = [
        {"ok": True, "status": "healed", "seconds": 5.0, "tokens": 100, "detail": ""},
        {"ok": True, "status": "healed", "seconds": 7.0, "tokens": 120, "detail": ""},
        {"ok": False, "status": "unhealed", "seconds": 40.0, "tokens": 0, "detail": "no proposal"},
    ]
    summary = summarize(results)
    assert summary["median_seconds"] == 6.0  # healed only -- comparable
    assert summary["median_seconds_all"] == 7.0  # raw, RCA included
    assert summary["accuracy_pct"] == 66.7
    assert summary["failure_modes"] == {"no proposal": 1}


def test_summarize_counts_wrong_element_heals():
    results = [
        {"ok": False, "status": "healed", "wrong_element": True, "seconds": 3.0, "tokens": 10, "detail": "x"},
        {"ok": True, "status": "healed", "seconds": 3.0, "tokens": 10, "detail": ""},
    ]
    assert summarize(results)["wrong_element"] == 1


def test_isolated_env_hides_ambient_heal_vars():
    os.environ["HEAL_LOCATOR_MODEL"] = "sneaky-model"
    try:
        with isolated_env() as stashed:
            assert "HEAL_LOCATOR_MODEL" not in os.environ
            assert "HEAL_LOCATOR_MODEL" in stashed
        assert os.environ["HEAL_LOCATOR_MODEL"] == "sneaky-model"  # restored
    finally:
        os.environ.pop("HEAL_LOCATOR_MODEL", None)


def test_sample_of_shipped_corpus_is_diverse():
    from heal.evals.corpus import load_corpus

    corpus = load_corpus(Path(__file__).parents[2] / "evals" / "fixtures")
    picked = stratified_sample(corpus, 12)
    suites = {p.name.rsplit("-", 1)[0] for p, _ in picked}
    assert len(picked) == 12
    # the old first-12 slice drew 11 of 12 from a single suite
    assert len(suites) >= 4
