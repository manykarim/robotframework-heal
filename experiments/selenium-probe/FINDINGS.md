# Findings: Selenium primitive probe (task 4.1)

**Date**: 2026-06-11 · SeleniumLibrary standalone + Selenium-Manager-provisioned headless Chrome · `probe.py`

| SessionDriver primitive | Selenium mechanism | Result |
|---|---|---|
| count / visibility | `driver.find_elements(By.CSS_SELECTOR/XPATH)` + `is_displayed()` | ok |
| ready state | `execute_script("return document.readyState")` | ok |
| element info / innerText | `execute_script("return arguments[0].innerText", el)` + `get_attribute` | ok |
| in-viewport | `getBoundingClientRect()` via execute_script | ok |
| scroll into view | `scrollIntoView({block:'center'})` via execute_script | ok |
| screenshot | `driver.get_screenshot_as_png()` (PNG bytes) | ok |
| page source | `driver.page_source` (property, not method) | ok — and current Chrome serializes open shadow content into it |
| shadow serialization | JS serializer (same approach as BrowserDriver) | ok |
| fill | `el.clear(); el.send_keys(...)` | ok |
| SL locator prefixes | `css:` and `xpath:` accepted by keywords | ok |

Caveats for the implementation:

1. **Proposal syntax differs**: heal proposals use `css=`/`xpath=`; SeleniumLibrary
   keywords accept `css:`/`xpath:`. The driver must translate when verifying
   (By.CSS_SELECTOR) and the heal outcome/rerun must emit SL-style (`css:`) locators.
2. **Selenium CSS does NOT pierce shadow roots** (even though Chrome's
   `page_source` shows shadow content) — shadow-DOM healing on Selenium is
   evidence-only/best-effort; verification will reject unreachable proposals.
3. **No frame piercing** — frame healing is detect+RCA only (design D5).
4. SeleniumLibrary works standalone via its public `driver` property; Selenium
   Manager auto-provisions the browser (no system chromedriver needed).
