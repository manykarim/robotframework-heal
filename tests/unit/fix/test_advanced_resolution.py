"""Advanced variable replacement: prefix shapes + keyword-argument tracing."""

import pytest

from heal.fix.apply import synthesize_changes
from heal.fix.resolve import resolve_fix

SUITE = """*** Settings ***
Resource    common.resource

*** Variables ***
${BTN_ID}         signin-btn
${LOGIN_BTN}      id=broken-login

*** Test Cases ***
Prefixed Variable
    Click    css=#${BTN_ID}

Keyword Arg Literal
    Click Login Button    id=broken-login

Keyword Arg Named
    Click Login Button    locator=id=broken-login

Keyword Arg Via Variable
    Press The Thing    ${LOGIN_BTN}
"""

RESOURCE = """*** Keywords ***
Click Login Button
    [Arguments]    ${locator}=id=default-login
    Log    clicking
    Click    ${locator}

Press The Thing
    [Arguments]    ${locator}
    Click    ${locator}

Click With Default Only
    [Arguments]    ${target}=id=broken-default
    Click    ${target}
"""


@pytest.fixture()
def tree(tmp_path):
    (tmp_path / "login.robot").write_text(SUITE, encoding="utf-8")
    (tmp_path / "common.resource").write_text(RESOURCE, encoding="utf-8")
    return tmp_path


def test_prefixed_variable_updates_definition(tree):
    fix = resolve_fix(
        file=str(tree / "login.robot"), lineno=10,
        old_locator="css=#signin-btn", new_locator="css=#login-submit",
    )
    assert fix.kind == "variable+suffix"
    assert fix.variable_name == "BTN_ID"
    assert fix.variable_new_value == "login-submit"

    result = synthesize_changes([fix])
    healed = next(c for c in result.changes if c.changed)
    assert "${BTN_ID}         login-submit" in healed.healed.replace("  ", "  ")
    assert "css=#${BTN_ID}" in healed.healed  # call site untouched


def test_prefix_mutation_falls_back_to_literal(tree):
    fix = resolve_fix(
        file=str(tree / "login.robot"), lineno=10,
        old_locator="css=#signin-btn", new_locator="xpath=//button[@id='x']",
    )
    assert fix.kind == "literal"
    assert fix.new_token == "xpath=//button[@id='x']"


def test_keyword_argument_traced_to_call_sites(tree):
    # failing call is `Click  ${locator}` inside the resource keyword (line 5)
    fix = resolve_fix(
        file=str(tree / "common.resource"), lineno=5,
        old_locator="id=broken-login", new_locator="css=#signin-btn",
        search_root=tree,
    )
    assert fix.kind == "keyword-argument"
    assert fix.variable_name == "locator"
    assert len(fix.call_site_edits) == 2  # positional + named call sites
    assert fix.blast_radius == "shared"

    result = synthesize_changes([fix])
    healed_suite = next(c for c in result.changes if c.path.endswith("login.robot"))
    assert "Click Login Button    css=#signin-btn" in healed_suite.healed
    assert "locator=css=#signin-btn" in healed_suite.healed
    # keyword body untouched
    assert not any(c.path.endswith("common.resource") and c.changed for c in result.changes)


def test_keyword_argument_via_variable_updates_variable(tree):
    fix = resolve_fix(
        file=str(tree / "common.resource"), lineno=9,
        old_locator="id=broken-login", new_locator="css=#signin-btn",
        search_root=tree,
    )
    assert fix.kind == "variable"
    assert fix.variable_name == "LOGIN_BTN"
    result = synthesize_changes([fix])
    healed = next(c for c in result.changes if c.path.endswith("login.robot"))
    assert "${LOGIN_BTN}      css=#signin-btn" in healed.healed


def test_keyword_argument_default_fixed_when_no_caller_overrides(tree):
    fix = resolve_fix(
        file=str(tree / "common.resource"), lineno=13,
        old_locator="id=broken-default", new_locator="css=#fixed-default",
        search_root=tree,
    )
    assert fix.kind == "keyword-argument"
    assert fix.call_site_edits[0][2] == "${target}=id=broken-default"
    result = synthesize_changes([fix])
    healed = next(c for c in result.changes if c.path.endswith("common.resource"))
    assert "${target}=css=#fixed-default" in healed.healed


def test_no_matching_call_site_unresolved(tree):
    fix = resolve_fix(
        file=str(tree / "common.resource"), lineno=9,
        old_locator="id=never-passed-anywhere", new_locator="css=#x",
        search_root=tree,
    )
    assert fix.kind == "unresolved"
