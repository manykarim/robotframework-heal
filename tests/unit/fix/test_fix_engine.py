"""Fix engine: origin resolution, blast radius, patches, tiered application.

Doubles as the 7.1 spike validation — runs against realistic RF files
(suite + imported resource + shared variables) created on disk.
"""

import subprocess
from pathlib import Path

import pytest

from heal.fix.apply import (
    apply_in_place,
    synthesize_changes,
    unified_patch,
    write_healed_copies,
)
from heal.fix.resolve import resolve_fix

SUITE = """*** Settings ***
Resource    common.resource

*** Variables ***
${LOCAL_BTN}      id=local-button

*** Test Cases ***
Literal Test
    Click    id=login-button
    Fill Text    id=user-email    tom

Variable Test
    Click    ${LOCAL_BTN}

Shared Variable Test
    Click    ${SHARED_BTN}

Suffix Test
    Click    ${MENU} li.first
"""

RESOURCE = """*** Variables ***
${SHARED_BTN}     id=shared-button
${MENU}           css=#menu

*** Keywords ***
Use Shared Button
    Click    ${SHARED_BTN}
    Log    uses shared
"""


@pytest.fixture()
def suite_dir(tmp_path):
    (tmp_path / "login.robot").write_text(SUITE, encoding="utf-8")
    (tmp_path / "common.resource").write_text(RESOURCE, encoding="utf-8")
    return tmp_path


def test_resolve_literal(suite_dir):
    fix = resolve_fix(
        file=str(suite_dir / "login.robot"), lineno=9,
        old_locator="id=login-button", new_locator="css=#signin-btn",
    )
    assert fix.kind == "literal"
    assert fix.blast_radius == "local"
    assert fix.new_token == "css=#signin-btn"


def test_resolve_variable_same_file(suite_dir):
    fix = resolve_fix(
        file=str(suite_dir / "login.robot"), lineno=13,
        old_locator="id=local-button", new_locator="id=renamed-button",
    )
    assert fix.kind == "variable"
    assert fix.variable_name == "LOCAL_BTN"
    assert fix.variable_file.endswith("login.robot")
    assert fix.variable_new_value == "id=renamed-button"
    assert fix.blast_radius == "local"  # single usage


def test_resolve_shared_variable_in_resource(suite_dir):
    fix = resolve_fix(
        file=str(suite_dir / "login.robot"), lineno=16,
        old_locator="id=shared-button", new_locator="id=new-shared",
    )
    assert fix.kind == "variable"
    assert fix.variable_file.endswith("common.resource")
    assert len(fix.usages) == 2  # suite + resource keyword
    assert fix.blast_radius == "shared"


def test_resolve_variable_with_suffix(suite_dir):
    fix = resolve_fix(
        file=str(suite_dir / "login.robot"), lineno=19,
        old_locator="css=#menu li.first", new_locator="css=#main-menu li.first",
    )
    assert fix.kind == "variable+suffix"
    assert fix.variable_name == "MENU"
    assert fix.variable_new_value == "css=#main-menu"


def test_resolve_unresolved(suite_dir):
    fix = resolve_fix(
        file=str(suite_dir / "login.robot"), lineno=9,
        old_locator="id=never-existed", new_locator="x",
    )
    assert fix.kind == "unresolved"


def test_synthesize_and_patch_git_appliable(suite_dir):
    subprocess.run(["git", "init", "-q"], cwd=suite_dir, check=True)
    subprocess.run(["git", "add", "-A"], cwd=suite_dir, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=suite_dir, check=True,
    )
    fixes = [
        resolve_fix(file=str(suite_dir / "login.robot"), lineno=9,
                    old_locator="id=login-button", new_locator="css=#signin-btn"),
        resolve_fix(file=str(suite_dir / "login.robot"), lineno=16,
                    old_locator="id=shared-button", new_locator="id=new-shared"),
    ]
    result = synthesize_changes(fixes)
    assert sorted(Path(p).name for p in result.changed_files) == ["common.resource", "login.robot"]

    patch = unified_patch(result, repo_root=suite_dir)
    assert "a/login.robot" in patch and "css=#signin-btn" in patch
    patch_file = suite_dir / "heal.patch"
    patch_file.write_text(patch, encoding="utf-8")
    check = subprocess.run(["git", "apply", "--check", "heal.patch"], cwd=suite_dir, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    subprocess.run(["git", "apply", "heal.patch"], cwd=suite_dir, check=True)
    assert "css=#signin-btn" in (suite_dir / "login.robot").read_text()
    assert "id=new-shared" in (suite_dir / "common.resource").read_text()
    # untouched lines stay byte-identical
    assert "Fill Text    id=user-email    tom" in (suite_dir / "login.robot").read_text()


def test_healed_copies(suite_dir, tmp_path):
    fixes = [resolve_fix(file=str(suite_dir / "login.robot"), lineno=9,
                         old_locator="id=login-button", new_locator="css=#signin-btn")]
    written = write_healed_copies(synthesize_changes(fixes), tmp_path / "healed")
    assert len(written) == 1
    assert "css=#signin-btn" in written[0].read_text()


def test_in_place_refused_on_dirty_tree(suite_dir):
    subprocess.run(["git", "init", "-q"], cwd=suite_dir, check=True)
    subprocess.run(["git", "add", "-A"], cwd=suite_dir, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=suite_dir, check=True,
    )
    suite = suite_dir / "login.robot"
    suite.write_text(suite.read_text() + "\n# local edit\n", encoding="utf-8")  # dirty

    fixes = [resolve_fix(file=str(suite), lineno=9,
                         old_locator="id=login-button", new_locator="css=#signin-btn")]
    written, refused = apply_in_place(synthesize_changes(fixes))
    assert written == [] and refused == [str(suite)]

    written, refused = apply_in_place(synthesize_changes(fixes), force=True)
    assert written == [str(suite)] and refused == []


def test_in_place_idempotent(suite_dir):
    suite = str(suite_dir / "login.robot")
    fixes = [resolve_fix(file=suite, lineno=9,
                         old_locator="id=login-button", new_locator="css=#signin-btn")]
    apply_in_place(synthesize_changes(fixes))
    # second application: nothing to change
    second = synthesize_changes(
        [resolve_fix(file=suite, lineno=9, old_locator="id=login-button", new_locator="css=#signin-btn")]
    )
    assert second.changed_files == []
    assert any("nothing to change" in s or "resolved" in s for s in second.skipped)
