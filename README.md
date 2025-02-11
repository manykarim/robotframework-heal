# robotframework-heal
A Robot Framework Listener for library agnostic self-healing and smart recovery of tests

📙 [Documentation](https://manykarim.github.io/robotframework-heal/) can be found [here](https://manykarim.github.io/robotframework-heal/)

## Installation
```bash
pip install robotframework-heal
```

## Usage

Add `Library    SelfHealing ` to your Robot Framework test suite `*** Settings ***` section.

```robotframework
*** Settings ***
Library    SelfHealing
```	

Set up the following environment variables to enable the self-healing feature:

* `LLM_API_KEY`
* `LLM_API_BASE`
* `LLM_TEXT_MODEL` (model used for picking final locator from proposal list)
* `LLM_LOCATOR_MODEL` (model for generating locator proposals from DOM tree)
* `LLM_VISION_MODEL` (not working yet)

Interface with LLMs uses the [LiteLMM](https://docs.litellm.ai) API.  
Check the list of available [Providers](https://docs.litellm.ai/docs/providers) and how to connect to them.  

```robotframework
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
    New Page    https://the-internet.herokuapp.com/login
    Fill Text    id=user    tomsmith
    Fill Text    id=pass    SuperSecretPassword!
    Click    id=loginbutton
    Get Text    id=flash    *=    You logged into a secure area!
```

## Arguments

* `fix`: Specifies the mode of operation, set to "realtime" for real-time healing. Default is "realtime".
* `collect_locator_info`: Boolean flag to enable or disable the collection of locator information. Default is false.
* `use_locator_db`: Boolean flag to enable or disable the use of a locator database. Default is false.
* `use_llm_for_locator_proposals`: Boolean flag to enable or disable the use of a language model for generating locator proposals. Default is false.
* `heal_assertions`: Boolean flag to enable or disable the healing of assertions. Default is false. (not implemented yet)
* `locator_db_file`: Specifies the filename for the locator database. Default is "locator_db.json".

## Environment Variables

Example when running with Ollama LLM:

```bash
LLM_API_BASE=http://localhost:11434
LLM_TEXT_MODEL=ollama_chat/llama3.1
LLM_LOCATOR_MODEL=ollama_chat/llama3.1
LLM_VISION_MODEL=ollama_chat/llama3.2-vision
```

Example when using OpenAI:

```bash
LLM_API_KEY=YOUR_OPENAI_API_KEY
LLM_TEXT_MODEL=gpt-3.5-turbo
LLM_LOCATOR_MODEL=gpt-3.5-turbo
```

## Open the project in Gitpod.io
[![Open in Gitpod](https://gitpod.io/button/open-in-gitpod.svg)](https://gitpod.io/#https://github.com/manykarim/robotframework-heal)  
Try it out in  [Gitpod](https://gitpod.io/#https://github.com/manykarim/robotframework-heal)

## Short URL and QR Code

https://tinyurl.com/robot-heal

![QR Code](QR-Code.png)