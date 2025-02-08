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
Add Two ToDos And Check Items
    [Documentation]    Checks if ToDos can be added and ToDo count increases
    [Tags]    Add ToDo
    Given ToDo App is open
    When I Add A New ToDo "Learn Robot Framework"
    And I Add A New ToDo "Write Test Cases"
    Then Open ToDos should show "2 items left!"

Add ToDo And Mark Same ToDo
    [Tags]    Mark ToDo
    Given ToDo App is open
    When I Add A New ToDo "Learn Robot Framework"
    And I Mark ToDo "Learn Robot Framework"
    Then Open ToDos should show "0 items left!"

Add Two ToDo And Mark ToDos
    [Tags]    Mark ToDo
    Given ToDo App is open
    When I Add A New ToDo "Learn Robot Framework"
    Then Open ToDos should show "1 item left!"
    When I Add A New ToDo "Write Tests"
    Then Open ToDos should show "2 items left!"
    When I Mark ToDo "Write Tests"
    And I Mark ToDo "Learn Robot Framework"
    Then Open ToDos should show "0 items left!"

*** Keywords ***
ToDo App is open
    New Page    https://todomvc.com/examples/react/dist/

I Add A New ToDo "${todo}"   
    Fill Text  .todo  ${todo}
    Press Keys  .todo  Enter
    
Open ToDos should show "${text}"
    Get Text    span.todo-count    ==    ${text}

I Mark ToDo "${todo}"
    Click    input.toggle >> "${todo}" 