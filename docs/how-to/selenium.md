# Use SeleniumLibrary

heal supports SeleniumLibrary through an optional extra.

## Install

```bash
pip install robotframework-heal[selenium]
```

## Add the listener

```robotframework
*** Settings ***
Library    SeleniumLibrary
Library    heal.rf.HealListener
Suite Teardown    Close All Browsers

*** Test Cases ***
Login
    Open Browser    https://example.com/login    headlesschrome
    Click Element    id=does-not-exist
```

Locator drift, viewport, overlay and form diagnosis all work. Proposals are
produced in SeleniumLibrary syntax (`css:…`, `xpath:…`).

## Limitations

- **iframes**: SeleniumLibrary has no frame-piercing selector syntax, so elements
  inside frames are **not healable** — heal detects this and produces a root-cause
  record naming the frame, rather than guessing.
- **Open shadow DOM**: best-effort via JS serialization; selectors that can't
  reach into a shadow root are rejected by verification.
- **Timing**: Selenium's default page-load strategy blocks commands until the
  document is ready, so timing failures rarely surface. To exercise timing
  healing, open with a non-blocking strategy:

  ```robotframework
  Open Browser    about:blank    headlesschrome    options=page_load_strategy="none"
  ```

See the [drivers reference](../reference/drivers.md) for the full capability matrix.
