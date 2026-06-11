from heal.fix.apply import FileChange
from heal.report.diff import (
    FixMapping,
    diff_rows,
    render_file_diff,
    write_diff_pages,
)

OLD = """*** Settings ***
Library    Browser

*** Test Cases ***
Login
    Click    id=login-button
    Get Text    id=status
"""

NEW = OLD.replace("id=login-button", "css=#signin-btn")


def test_rows_and_stats():
    rows, stats = diff_rows(OLD, NEW)
    assert stats.changed == 1 and stats.added == 0 and stats.removed == 0
    changed = [r for r in rows if r.kind == "chg"]
    assert len(changed) == 1
    assert changed[0].left_no == 6 and changed[0].right_no == 6


def test_intraline_highlights_only_the_changed_token():
    page, _ = render_file_diff(OLD, NEW, file_label="login.robot")
    assert '<span class="hl-del">id=login-button</span>' in page
    assert '<span class="hl-ins">css=#signin-btn</span>' in page
    # the keyword name on the same line is NOT highlighted
    assert '<span class="hl-del">Click' not in page


def test_header_mappings_and_self_containment():
    page, _ = render_file_diff(
        OLD, NEW, file_label="login.robot",
        mappings=[FixMapping("id=login-button", "css=#signin-btn", "shared")],
    )
    assert "b-shared" in page
    assert "original file is untouched" in page
    assert "<script" not in page and "href=\"http" not in page and "@import" not in page


def test_context_folding_on_large_files():
    old = "\n".join(f"line {i}" for i in range(200)) + "\nTARGET old\n"
    new = old.replace("TARGET old", "TARGET new")
    page, stats = render_file_diff(old, new, file_label="big.robot")
    assert stats.changed == 1
    assert "unchanged line(s)" in page  # folded run
    assert page.count('class="fold"') >= 1


def test_insert_delete_and_edge_cases():
    rows, stats = diff_rows("a\nb\n", "a\nb\nc\n")
    assert stats.added == 1 and [r.kind for r in rows][-1] == "ins"
    rows, stats = diff_rows("a\nb\nc\n", "a\nc\n")
    assert stats.removed == 1
    # empty + EOL-less + unicode must not raise
    render_file_diff("", "x", file_label="e")
    render_file_diff("no eol", "no eol changed", file_label="e")
    page, _ = render_file_diff("Grüße <&>", "Grüße neu <&>", file_label="ünïcode.robot")
    assert "&lt;&amp;&gt;" in page


def test_write_diff_pages_and_index(tmp_path):
    changes = [
        FileChange(path="/suites/login.robot", original=OLD, healed=NEW),
        FileChange(path="/suites/same.robot", original=OLD, healed=OLD),  # unchanged: skipped
    ]
    pages = write_diff_pages(
        changes, tmp_path, {"/suites/login.robot": [FixMapping("id=login-button", "css=#signin-btn")]}
    )
    assert len(pages) == 1
    assert pages[0].path.name == "login.diff.html"
    index = (tmp_path / "index.html").read_text()
    assert "login.diff.html" in index and "same.robot" not in index
