*** Settings ***
Library    Browser    timeout=5s
Library    String
Library    SelfHealing    use_llm_for_locator_proposals=False    heal_assertions=True
Suite Setup    New Browser    browser=${BROWSER}    headless=${HEADLESS}
Test Setup    New Context    viewport={'width': 1280, 'height': 720}
Test Teardown    Close Context
Suite Teardown    Close Browser    ALL

*** Variables ***
${BROWSER}    chromium
${HEADLESS}    True

*** Test Cases ***
Add ToDo And Check Wrong Number
    [Tags]    Mark ToDo    robot:skip-on-failure
    New Page    https://todomvc.com/examples/react/dist/
    Fill Text  .new-todo  Learn Robot Framework
    Press Keys  .new-todo  Enter
    Fill Text  .new-todo  Write Tests
    Press Keys  .new-todo  Enter
    Click    "Learn Robot Framework" >> .. >> input.toggle
    Get Text    span.todo-count    ==    2 items left!


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