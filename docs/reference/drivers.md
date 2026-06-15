# Drivers

heal talks to the live session through a `SessionDriver` — one protocol, one
implementation per automation library. The listener picks the driver from the
failing keyword's owning library; failures from libraries without a driver are
left untouched.

| Capability | Browser (Playwright) | SeleniumLibrary | AppiumLibrary |
|---|---|---|---|
| Install | included | `pip install robotframework-heal[selenium]` | included |
| Locator drift | ✅ | ✅ | ✅ |
| Timing recovery | ✅ | ✅ (see note) | ✅ (no-op ready) |
| Viewport recovery | ✅ scroll | ✅ scroll | ✅ bounded swipe search |
| Overlay dismissal | ✅ | ✅ | ✅ permission popups |
| Form diagnosis | ✅ | ✅ | DOM-only |
| Open shadow DOM | ✅ pierced | ⚠️ best-effort (JS serialize, no pierce selectors) | n/a |
| Closed shadow DOM | ❌ platform-restricted | ❌ | n/a |
| iframes | ✅ `frame >>> inner` healing | ❌ detect + RCA only (no pierce syntax) | n/a |

!!! note "SeleniumLibrary timing"
    Selenium's default page-load strategy blocks commands until the document is
    ready, so timing failures rarely surface. They appear (and heal) with
    `page_load_strategy=none`.

## How the driver is selected

```text
owning RF library   ->  driver
Browser             ->  BrowserDriver    (Playwright)
SeleniumLibrary     ->  SeleniumDriver   (optional [selenium] extra)
AppiumLibrary       ->  AppiumDriver
```

All driver calls are marshalled to the Robot Framework main thread — see
[Threading and execution](../explanation/threading.md).

## Locator syntax per library

Proposals are produced in the library's own syntax:

- **Browser**: `css=…`, `xpath=…`, frame-pierced `id=frame >>> css=#btn`
- **SeleniumLibrary**: `css:…`, `xpath:…`
- **AppiumLibrary**: `xpath=…`, `accessibility_id=…`, `id=…`, `class=…`
