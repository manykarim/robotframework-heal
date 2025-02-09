*** Settings ***
Library    Browser    timeout=5s
Library    SelfHealing    use_llm_for_locator_proposals=False
Suite Setup    New Browser    browser=${BROWSER}    headless=${HEADLESS}
Test Setup    New Context    viewport={'width': 1280, 'height': 720}
Test Teardown    Close Context
Suite Teardown    Close Browser    ALL

*** Variables ***
${BROWSER}    chromium
${HEADLESS}    True

*** Test Cases ***
Login with valid credentials
    New Page    https://www.saucedemo.com/
    Fill Text    id=user    standard_user
    Fill Text    id=pass    secret_sauce
    Click    id=loginbutton
    Get Url    ==    https://www.saucedemo.com/inventory.html

Add Product To Cart
    Login
    Click    Sauce Labs Onesie >> Add To Cart
    Get Text    shopping_cart    ==    1


*** Keywords ***
Login
    New Page    https://www.saucedemo.com/
    Fill Text    css=input#user-name    standard_user
    Fill Text    css=input#password    secret_sauce
    Click    css=input#login-button
    Get Url    ==    https://www.saucedemo.com/inventory.html