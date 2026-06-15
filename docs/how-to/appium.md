# Use AppiumLibrary

heal supports AppiumLibrary out of the box (no extra needed).

## Add the listener

```robotframework
*** Settings ***
Library    AppiumLibrary
Library    Heal
```

## Mobile specifics

The mobile page source describes only the **current screen**, so an element that
is off-screen is *absent*, not merely hidden. heal accounts for this:

- **Viewport / off-screen** failures trigger a **bounded swipe search** — heal
  swipes toward the element (down, then back up) up to a fixed number of times,
  confirming visibility, then reruns. If swiping finds nothing, the failure
  falls through to locator-drift healing (the element may have been renamed).
- **Locator proposals** for mobile are verified with the same swipe search, so a
  proposed off-screen element is brought into view before it is accepted.
- **Permission popups** (e.g. "ALLOW") are recognised and dismissed as overlays.

Proposals use AppiumLibrary syntax: `xpath=…`, `accessibility_id=…`, `id=…`,
`class=…`.

See the [drivers reference](../reference/drivers.md) for the capability matrix.
