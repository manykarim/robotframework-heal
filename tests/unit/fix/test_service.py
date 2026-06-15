"""Always-on fix artifacts: copies + diffs, originals untouched, dashboard views."""

from heal.core.schemas import BlastRadius, FixProposal, HealEvent
from heal.fix.service import build_fix_artifacts

SUITE = """*** Test Cases ***
Login
    Click    id=login-button
    Get Text    id=status
"""


def make_event(file, old="id=login-button", new="css=#signin-btn"):
    return HealEvent(
        event_id="e1",
        source=file,
        lineno=3,
        fix_proposal=FixProposal(
            file=file, lineno=3, kind="locator",
            old_value=old, new_value=new, blast_radius=BlastRadius.LOCAL,
        ),
    )


def test_artifacts_created_and_original_untouched(tmp_path):
    suite = tmp_path / "login.robot"
    suite.write_text(SUITE, encoding="utf-8")
    before = suite.read_bytes()
    out = tmp_path / "heal"

    artifacts = build_fix_artifacts([make_event(str(suite))], out)

    assert suite.read_bytes() == before  # original byte-identical
    healed = out / "healed_files" / tmp_path.name / "login.robot"
    assert healed.is_file() and "css=#signin-btn" in healed.read_text()
    diff_page = out / "diffs" / "login.diff.html"
    assert diff_page.is_file()
    page = diff_page.read_text()
    assert "hl-del" in page and "css=#signin-btn" in page
    assert (out / "diffs" / "index.html").is_file()

    key = f"{suite}|id=login-button|css=#signin-btn"
    view = artifacts.proposal_views[key]
    assert view["link"] == "diffs/login.diff.html"
    assert "table" in view["inline"] and "css=#signin-btn" in view["inline"]


def test_no_proposals_no_artifacts(tmp_path):
    out = tmp_path / "heal"
    artifacts = build_fix_artifacts([HealEvent(event_id="x")], out)
    assert artifacts.proposals == []
    assert not (out / "diffs").exists()


def test_missing_source_degrades_gracefully(tmp_path):
    artifacts = build_fix_artifacts([make_event(str(tmp_path / "gone.robot"))], tmp_path / "heal")
    assert artifacts.result.changed_files == []
    assert artifacts.proposal_views == {}
