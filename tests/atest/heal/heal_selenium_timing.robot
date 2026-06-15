*** Settings ***
Documentation     Timing-class healing on SeleniumLibrary (no LLM): keyword fails
...               while the page is loading; the engine waits for ready and reruns.
Library           SeleniumLibrary
Library           Process
Library           Heal
Suite Setup       Start Slow Server
Suite Teardown    Run Keywords    Close All Browsers    AND    Stop Slow Server
Force Tags        heal-atest

*** Variables ***
${PORT}           8766

*** Test Cases ***
Selenium Keyword Failing During Load Is Healed By Waiting
    [Documentation]    page_load_strategy=none: commands don't block on navigation,
    ...    so the click fails mid-load — the timing plugin must wait and rerun.
    Open Browser    about:blank    headlesschrome    options=page_load_strategy="none"
    Go To Slow Page
    Click Element    id=late-btn
    Element Text Should Be    id=marker    late-clicked

*** Keywords ***
Start Slow Server
    ${process} =    Start Process    python    ${CURDIR}/slow_server.py    ${PORT}
    Set Suite Variable    ${SERVER}    ${process}
    Sleep    0.5s

Stop Slow Server
    Terminate Process    ${SERVER}    kill=True

Go To Slow Page
    Execute Javascript    window.location='http://127.0.0.1:${PORT}/slow_load.html'
    Sleep    0.3s
