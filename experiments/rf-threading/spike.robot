*** Settings ***
Documentation     Threading spike for design D4 (healer loop + main-thread executor).

*** Test Cases ***
Heal A Failing Keyword With Assignment
    ${value} =    Should Be Equal    wrong-value    corrected-value
    Should Be Equal    ${value}    corrected-value
    Log    assignment after heal works: ${value}

Healed Run Continues Normally
    Log    second test still runs
    ${value} =    Should Be Equal    also-wrong    corrected-value
    Should Be Equal    ${value}    corrected-value

Abandoned Transaction Unblocks The Run
    [Documentation]    The listener hangs its transaction; the run must continue.
    Run Keyword And Expect Error    *    Hang Forever Keyword

After Abandonment Life Goes On
    Log    still alive after abandonment

*** Keywords ***
Hang Forever Keyword
    Fail    triggers-hanging-transaction
