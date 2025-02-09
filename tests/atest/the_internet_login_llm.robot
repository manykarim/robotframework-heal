*** Settings ***
Library    Browser    timeout=5s
Library    String
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
    New Page    https://the-internet.herokuapp.com/login
    Fill Text    id=user    tomsmith
    Fill Text    id=pass    SuperSecretPassword!
    Click    id=loginbutton
    Get Text    id=flash    *=    You logged into a secure area!