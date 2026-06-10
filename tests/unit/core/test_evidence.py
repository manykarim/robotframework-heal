from pathlib import Path

from heal.core.evidence import MAX_DOM_CHARS, ContextBuilder
from heal.core.gitinfo import file_git_info
from heal.core.schemas import EvidenceKind, KeywordCall


class FakeDriver:
    def __init__(self, dom="<body><form id='f'/></body>", png=b"\x89PNG fake"):
        self.dom = dom
        self.png = png
        self.dom_calls = 0

    def get_simplified_dom(self):
        self.dom_calls += 1
        return self.dom

    def take_screenshot(self):
        return self.png


def make_builder(tmp_path, driver=None, source=None, lineno=None):
    return ContextBuilder(
        keyword=KeywordCall(name="Click", args=["id=x"], owner_library="Browser", lineno=lineno, source=source),
        error_message="boom",
        test_name="T",
        suite_name="S",
        failed_locator="id=x",
        driver=driver,
        artifact_dir=tmp_path / "artifacts",
    )


def test_lazy_collection_and_caching(tmp_path):
    driver = FakeDriver()
    builder = make_builder(tmp_path, driver)

    ctx = builder.context()
    assert ctx.evidence == {}
    assert driver.dom_calls == 0  # nothing collected until requested

    ctx = builder.context(EvidenceKind.DOM_EXCERPT)
    assert ctx.evidence_of(EvidenceKind.DOM_EXCERPT).excerpt.startswith("<body>")
    builder.context(EvidenceKind.DOM_EXCERPT)
    assert driver.dom_calls == 1  # cached, not re-collected


def test_dom_excerpt_is_bounded(tmp_path):
    driver = FakeDriver(dom="x" * (MAX_DOM_CHARS + 5000))
    ctx = make_builder(tmp_path, driver).context(EvidenceKind.DOM_EXCERPT)
    ev = ctx.evidence_of(EvidenceKind.DOM_EXCERPT)
    assert len(ev.excerpt) == MAX_DOM_CHARS
    assert "truncated" in ev.summary


def test_screenshot_saved_to_artifact_dir(tmp_path):
    ctx = make_builder(tmp_path, FakeDriver()).context(EvidenceKind.SCREENSHOT)
    ev = ctx.evidence_of(EvidenceKind.SCREENSHOT)
    assert ev is not None
    assert Path(ev.path).read_bytes() == b"\x89PNG fake"


def test_source_excerpt_marks_failing_line(tmp_path):
    suite = tmp_path / "login.robot"
    suite.write_text("\n".join(f"line {i}" for i in range(1, 40)), encoding="utf-8")
    builder = make_builder(tmp_path, source=str(suite), lineno=20)
    ev = builder.context(EvidenceKind.SOURCE_EXCERPT).evidence_of(EvidenceKind.SOURCE_EXCERPT)
    assert ">> 20: line 20" in ev.excerpt
    assert "   10: line 10" in ev.excerpt and "31: line 31" not in ev.excerpt


def test_collector_failure_yields_absent_evidence(tmp_path):
    class BrokenDriver:
        def get_simplified_dom(self):
            raise RuntimeError("browser gone")

        def take_screenshot(self):
            raise RuntimeError("browser gone")

    ctx = make_builder(tmp_path, BrokenDriver()).context(
        EvidenceKind.DOM_EXCERPT, EvidenceKind.SCREENSHOT
    )
    assert ctx.evidence == {}


def test_git_history_for_tracked_file(tmp_path):
    # this repo file is tracked -> info available (skip-free: repo always has git)
    tracked = Path(__file__).resolve().parents[3] / "pyproject.toml"
    info = file_git_info(str(tracked))
    assert info.available
    assert info.last_modified

    builder = make_builder(tmp_path, source=str(tracked), lineno=1)
    ev = builder.context(EvidenceKind.GIT_HISTORY).evidence_of(EvidenceKind.GIT_HISTORY)
    assert ev is not None and "last modified" in ev.summary


def test_git_history_absent_outside_repo(tmp_path):
    loose = tmp_path / "loose.robot"
    loose.write_text("x", encoding="utf-8")
    assert not file_git_info(str(loose)).available
