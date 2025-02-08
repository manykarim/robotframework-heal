*** Settings ***
Library    Browser    timeout=5s
Library    String
Library    SelfHealing    use_llm_for_locator_proposals=False
Suite Setup    New Browser    browser=${BROWSER}    headless=${HEADLESS}
Test Setup    New Context    viewport={'width': 1280, 'height': 720}
Test Teardown    Close Context
Suite Teardown    Close Browser    ALL

*** Variables ***
${BROWSER}    chromium
${HEADLESS}    True


*** Test Cases ***
Enter New Car
    New Page    http://car.keyword-driven.de/login
    Fill Text    User    user01
    Fill Text    Password    password
    Click    Login
    Click    Neues Auto
    Select Options By    Basismodell    text    Rassant
    Click    Arrow Right
    Click    Jazz
    Click    Arrow Right

Find the Login Button
    New Page    http://car.keyword-driven.de/login
    Fill Text    id=input_username    user01
    Fill Text    id=input_password    password
    Click    Login
    Wait For Elements State   "Neues Auto"
