*** Settings ***
Library           Browser    timeout=3s
Library           SelfHealing
Suite Setup       New Browser    chromium    headless=True
Suite Teardown    Close Browser    ALL
Test Setup        New Context
Force Tags        live-llm
Force Tags        live-llm

*** Variables ***
${PAGES}          ${CURDIR}/pages

*** Test Cases ***
Broken Locator Inside Open Shadow DOM
    [Documentation]    Real button is #shadow-submit, two shadow roots deep.
    New Page    file://${PAGES}/shadow.html
    Click    id=submit-button
    Get Text    id=status    ==    shadow-clicked

Locator Inside Closed Shadow Root
    [Documentation]    Closed roots are invisible; expect unhealable + RCA.
    New Page    file://${PAGES}/shadow.html
    Run Keyword And Expect Error    *    Click With Options    id=closed-btn    timeout=2s

Broken Locator Inside Iframe
    [Documentation]    Real button is #frame-submit inside iframe#content-frame.
    New Page    file://${PAGES}/frames.html
    Click    id=send-button
    Get Text    id=content-frame >>> id=frame-status    ==    frame-clicked
