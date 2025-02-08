*** Settings ***
Library    AppiumLibrary
Library    Process
Library    OperatingSystem
Library    SelfHealing    use_llm_for_locator_proposals=False
Test Tags    appium    not_ci

*** Variables ***
${ANDROID_AUTOMATION_NAME}    UIAutomator2
${ANDROID_APP}                ${CURDIR}${/}demoapp${/}SauceLabsDemo.apk
${ANDROID_PLATFORM_NAME}      Android
${ANDROID_PLATFORM_VERSION}   %{ANDROID_PLATFORM_VERSION=8}

*** Test Cases ***
Start Demo App with broken username and password
    Open Test Application
    Wait Until Element Is Visible    //android.widget.EditText[@text,"Username"]

    Input Text    //android.widget.EditText[@content-desc="User"]    standard_user
    Input Text    //android.widget.EditText[@content-desc="Password"]    secret_sauce    
    Click Element    Login
    Wait Until Page Contains    text=PRODUCTS


Select Product not in view
    Open Test Application
    Login
    Click Element    //android.widget.TextView[@text="Sauce Labs Onesie"]


Close unexpected permission popup
    Open Test Application
    Login
    Click Element    //android.view.ViewGroup[@content-desc="test-Menu"]
    Click Element    //android.widget.TextView[contains(@text, 'QR CODE SCANNER')]
    Sleep    1
    Click Element    //android.view.View[@resource-id="com.swaglabsmobileapp:id/texture_view"]

Start Demo App With Correct Locators
    Open Test Application
    Login
    Add Product "Sauce Labs Backpack"
    Number Of Cart Items Should Be "1"
    Add Product "Sauce Labs Onesie"
    Number Of Cart Items Should Be "2"

*** Keywords ***
Start Device
    ${emulator}    Start Process    emulator    -avd    Pixel_26    stdout=stdout.log    stderr=stderr.log
Open Test Application
  Open Application  http://127.0.0.1:4723  automationName=${ANDROID_AUTOMATION_NAME}
  ...  platformName=${ANDROID_PLATFORM_NAME}  platformVersion=${ANDROID_PLATFORM_VERSION}
  ...  appPackage=com.swaglabsmobileapp  appActivity=com.swaglabsmobileapp.MainActivity
  ...  newCommandTimeout=300

Login
    Wait Until Element Is Visible    //android.widget.EditText[@text,"Username"]
    ${html}    Get Source
    Create File    login.html    ${html}
    Input Text    //android.widget.EditText[@text="Username"]    standard_user
    Input Text    //android.widget.EditText[@text="Password"]    secret_sauce    
    Click Element    //android.widget.TextView[@text="LOGIN"]
    Wait Until Page Contains    text=PRODUCTS

Click On Product "${text}"
    ${html}    Get Source
    Create File    products_top_${text}.html    ${html}
    Swipe Until Element Is Visible    //android.widget.TextView[@text="${text}"]
    ${html}    Get Source
    Create File    products_scrolled_${text}.html    ${html}

    Click Element    //android.widget.TextView[@text="${text}"]

Add To Cart
    Wait Until Page Contains    text=BACK TO PRODUCTS
    Swipe Until Element Is Visible    //android.widget.TextView[@text="ADD TO CART"]
    Click Element    //android.widget.TextView[@text="ADD TO CART"]

Swipe Until Element Is Visible
    [Arguments]    ${locator}
    ${element_found}    Run Keyword And Return Status    Page Should Contain Element    ${locator}
    WHILE  not ${element_found}    limit=10
        Swipe By Percent    0    80    0    20
        ${element_found}    Run Keyword And Return Status    Page Should Contain Element    ${locator}  
    END

Back To Products
    Click Element    //*[@text="BACK TO PRODUCTS"]
    Wait Until Page Does Not Contain    BACK TO PRODUCTS

Add Product "${text}"
    Click On Product "${text}"
    Add To Cart
    Back To Products

Number Of Cart Items Should Be "${count}"
    ${text}    Get Text    locator=//android.view.ViewGroup[@content-desc="test-Cart"]//android.widget.TextView
    Should Be Equal As Numbers    ${count}    ${text}