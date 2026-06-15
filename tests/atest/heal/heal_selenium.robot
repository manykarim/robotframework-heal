*** Settings ***
Documentation     SeleniumLibrary healing parity: locator drift on the shared demo page.
...               Requires HEAL_MODEL/HEAL_BASE_URL/HEAL_API_KEY (live LLM).
Library           SeleniumLibrary
Library           Heal
Suite Teardown    Close All Browsers
Force Tags        live-llm

*** Variables ***
${DEMO_PAGE}      ${CURDIR}/pages/login_drift.html

*** Test Cases ***
Broken Locator Is Healed On Selenium
    [Documentation]    id=login-button does not exist; the engine must find signin-btn.
    Open Browser    file://${DEMO_PAGE}    headlesschrome
    Click Element    id=login-button
    Element Text Should Be    id=status    clicked

Known Fix Is Reused On Selenium
    Go To    file://${DEMO_PAGE}
    Click Element    id=login-button
    Element Text Should Be    id=status    clicked
