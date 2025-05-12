*** Settings ***
Library    Browser    timeout=5s
Library    SelfHealing    use_llm_for_locator_proposals=True
Suite Setup    New Browser    browser=${BROWSER}    headless=${HEADLESS}
Test Setup    New Context    viewport={'width': 1280, 'height': 720}
Test Teardown    Close Context
Suite Teardown    Close Browser    ALL

*** Variables ***
${BROWSER}    chromium
${HEADLESS}    True

*** Test Cases ***
Login with valid credentials
    New Page    https://automationintesting.com/selenium/testpage/
    Set Browser Timeout    1s
    ${status}    Run Keyword And Return Status   Fill Text    id=first_name    tom
    Should Be Equal    ${status}    ${False}