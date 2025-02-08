*** Settings ***
Library    Browser
Library    SelfHealing    use_llm_for_locator_proposals=True
Suite Setup    New Browser    browser=${BROWSER}    headless=${HEADLESS}
Test Teardown    Close Context
Suite Teardown    Close Browser    ALL

*** Variables ***
${BROWSER}    chromium
${HEADLESS}    True

*** Test Cases ***
Create Quote for Car
    Open Insurance Application
    Enter Vehicle Data for Automobile
    Check Entered Vehicle Data

*** Keywords ***
Open Insurance Application
    New Context    locale=en-GB    
    Set Browser Timeout    30
    New Page    http://sampleapp.tricentis.com/

Enter Vehicle Data for Automobile
    Click    div.main-navigation >> "Automobile"
    Set Browser Timeout    1
    Select Options By    Make    text    Audi
    Fill Text    Engine Performance    110
    Fill Text    Date of Manufacture    06/12/1980
    Select Options By    Number of Seats    text    5
    Select Options By    Fuel Type    text    Petrol    
    Fill Text    List Price    30000
    Fill Text    License Plate Number    DEF1234
    Fill Text    Annual Mileage   10000

Check Entered Vehicle Data
    Get Selected Options   Make    text    ==    Audi
    Get Text    Engine Performance    ==    110
    Get Text    Date of Manufacture    ==    06/12/1980
    Get Selected Options    Number of Seats    text    ==    5
    Get Selected Options    Fuel Type    text    ==    Petrol    
    Get Text    List Price    ==    30000
    Get Text    License Plate Number    ==    DEF1234
    Get Text    Annual Mileage   ==    10000
    
Enter Insurant Data
    [Arguments]    ${firstname}=Max    ${lastname}=Mustermann
    Fill Text    id=firstname    Max
    Fill Text    id=lastname    Mustermann
    Fill Text    id=birthdate    01/31/1980
    Check Checkbox    *css=label >> id=gendermale
    Fill Text    id=streetaddress    Test Street
    Select Options By    id=country    text    Germany
    Fill Text    id=zipcode    40123
    Fill Text    id=city    Essen
    Select Options By    id=occupation    text    Employee
    Click    text=Cliff Diving
    Click    section[style="display: block;"] >> text=Next »

Enter Product Data
    Fill Text    id=startdate    06/01/2025
    Select Options By    id=insurancesum    text    7.000.000,00
    Select Options By    id=meritrating    text    Bonus 1
    Select Options By    id=damageinsurance    text    No Coverage
    Check Checkbox    *css=label >> id=EuroProtection
    Select Options By    id=courtesycar    text    Yes
    Click    section[style="display: block;"] >> text=Next »

Select Price Option
    [Arguments]    ${price_option}=Silver
    Click    *css=label >> css=[value=${price_option}]
    Click    section[style="display: block;"] >> text=Next »

Send Quote
    Fill Text    "E-Mail" >> .. >> input    max.mustermann@example.com
    Fill Text    "Phone" >> .. >> input    0049201123456
    Fill Text    "Username" >> .. >> input    max.mustermann
    Fill Text    "Password" >> .. >> input    SecretPassword123!
    Fill Text    "Confirm Password" >> .. >> input    SecretPassword123!
    Fill Text    "Comments" >> .. >> textarea    Some comments
    ${promise}=     Promise To    Wait For Response     matcher=http://sampleapp.tricentis.com/101/tcpdf/pdfs/quote.php     timeout=10
    Click    "« Send »"
    ${body}=    Wait For    ${promise}
    Log    ${body}[status]
    Log    ${body}[body]
    Wait For Elements State    "Sending e-mail success!"
    Click    "OK"