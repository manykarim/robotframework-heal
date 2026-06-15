*** Settings ***
Documentation     Timing-class healing (no LLM needed): keyword fails while the
...               page is still loading; the engine waits for ready and reruns.
Library           Browser    timeout=2s
Library           Process
Library           Heal
Suite Setup       Start Slow Server
Suite Teardown    Stop Slow Server
Force Tags        heal-atest

*** Variables ***
${PORT}           8765

*** Test Cases ***
Keyword Failing During Load Is Healed By Waiting
    New Browser    chromium    headless=True
    New Context
    Go To Slow Page
    Click    id=late-btn
    Get Text    id=marker    ==    late-clicked
    [Teardown]    Close Browser    ALL

*** Keywords ***
Start Slow Server
    ${process} =    Start Process    python    ${CURDIR}/slow_server.py    ${PORT}
    Set Suite Variable    ${SERVER}    ${process}
    Sleep    0.5s

Stop Slow Server
    Terminate Process    ${SERVER}    kill=True

Go To Slow Page
    New Page
    Go To    http://127.0.0.1:${PORT}/slow_load.html    wait_until=domcontentloaded
