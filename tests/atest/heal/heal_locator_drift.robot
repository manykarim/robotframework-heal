*** Settings ***
Documentation     Locator-drift healing end-to-end through the Heal listener.
...               Requires HEAL_MODEL/HEAL_BASE_URL/HEAL_API_KEY (live LLM).
Library           Browser    timeout=3s
Library           Heal
Suite Setup       New Browser    chromium    headless=True
Suite Teardown    Close Browser    ALL
Test Setup        Open Demo Page
Force Tags        live-llm

*** Variables ***
${DEMO_PAGE}      ${CURDIR}/pages/login_drift.html

*** Test Cases ***
Broken Locator Is Healed At Runtime
    [Documentation]    id=login-button does not exist; the engine must find signin-btn.
    Click    id=login-button
    Get Text    id=status    ==    clicked

Known Fix Is Reused Without New Healing
    [Documentation]    Same broken locator again: greedy reuse swaps it pre-execution.
    Click    id=login-button
    Get Text    id=status    ==    clicked

*** Keywords ***
Open Demo Page
    New Context
    New Page    file://${DEMO_PAGE}
