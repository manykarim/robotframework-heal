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
    New Page    https://automationintesting.com/selenium/testpage/
    Set Browser Timeout    1s
    Fill Text    id=first_name    tom
    Fill Text    id=last_name    smith
    Select Options By    id=usergender    label    Male
    Click    id=red
    Fill Text    id=tell_me_more    More information
    Select Options By    id=user_continent    label    Africa
    Click    id=i_do_nothing