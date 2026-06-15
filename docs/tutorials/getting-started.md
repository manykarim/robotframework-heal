# Getting started

In five minutes you'll watch heal repair a deliberately broken locator at runtime
and produce a report. You need Python 3.10+, a Robot Framework Browser setup, and
access to any OpenAI-compatible model endpoint.

## 1. Install

```bash
pip install robotframework-heal
rfbrowser init    # one-time Playwright browser download
```

## 2. Configure a model

Create a `.env` in your project root (the nearest `.env` is loaded automatically
and overrides the environment):

```bash
HEAL_MODEL=openai/gpt-4.1-nano
HEAL_BASE_URL=https://openrouter.ai/api/v1
HEAL_API_KEY=sk-...
```

Any OpenAI-compatible endpoint works — see [Configure a model provider](../how-to/model-providers.md)
for vLLM, Ollama, MiniMax, Azure and others. Check it before running:

```bash
heal doctor --role locator
```

## 3. Add the listener

```robotframework
*** Settings ***
Library    Browser    timeout=3s
Library    Heal
Suite Setup       New Browser    chromium    headless=True
Suite Teardown    Close Browser    ALL

*** Test Cases ***
Login
    New Page    https://the-internet.herokuapp.com/login
    # this id is wrong on purpose — heal will find the real one
    Click    id=does-not-exist
```

## 4. Run it

```bash
robot -d results login.robot
```

You'll see heal classify the failure, propose a verified locator, rerun the
keyword, and pass the test:

```text
heal: 'Click' failed (locator-drift) and was healed:
      Replaced broken locator 'id=does-not-exist' with verified 'css=...'.
```

## 5. Read the report

Open `results/heal/heal_report.html` — the dashboard shows the healed failure,
the evidence, the cost, and a **fix proposal** with a side-by-side diff of the
suggested permanent change (your original file is untouched). See
[What you get](../what-you-get.md) for a tour of the artifacts.

## Next steps

- [Configure a model provider](../how-to/model-providers.md) for your backend
- [Fix test files](../how-to/fixing-files.md) to turn heals into permanent changes
- [Failure taxonomy](../explanation/failure-taxonomy.md) to understand what heal can repair
