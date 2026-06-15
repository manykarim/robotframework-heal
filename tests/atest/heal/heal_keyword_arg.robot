*** Settings ***
Documentation     Keyword-argument flow: the broken literal lives at the CALL SITE;
...               the fix must land there, never inside the resource keyword body.
Library           Browser    timeout=3s
Library           Heal
Resource          resources/clicks.resource
Suite Setup       New Browser    chromium    headless=True
Suite Teardown    Close Browser    ALL
Force Tags        live-llm

*** Variables ***
${DEMO_PAGE}      ${CURDIR}/pages/login_drift.html

*** Test Cases ***
Broken Literal At Call Site Is Healed And Fixed There
    New Context
    New Page    file://${DEMO_PAGE}
    Click Via Keyword    id=login-button
    Get Text    id=status    ==    clicked
