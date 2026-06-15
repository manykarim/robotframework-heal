# runtime-recovery Specification

## Purpose
TBD - created by archiving change agentic-heal-rewrite. Update Purpose after archive.
## Requirements
### Requirement: Timing recovery
WHEN a failure is classified `timing` (document not ready, pending navigation/network), the engine SHALL wait for the page-ready condition up to a configured timeout and rerun the original keyword, without any LLM call.

#### Scenario: Slow page load healed by waiting
- **WHEN** a keyword fails while `document.readyState != 'complete'`
- **THEN** the engine waits for load completion (bounded by `HEAL_READY_TIMEOUT`) and reruns the keyword

### Requirement: Viewport recovery
WHEN a failure is classified `viewport` (element exists in DOM but is outside the visible viewport), the engine SHALL scroll (web) or swipe (Appium) the element into view and rerun the keyword, without any LLM call for the scroll action.

#### Scenario: Appium element below the fold
- **WHEN** an Appium keyword fails and the element exists but is not visible
- **THEN** the engine swipes toward the element (bounded number of swipes), confirms visibility, and reruns the keyword

#### Scenario: Element not found at all is not viewport
- **WHEN** the element matches 0 elements in the DOM/page source
- **THEN** the failure is NOT classified `viewport` (falls through to locator-drift detection)

### Requirement: Overlay recovery
WHEN a failure is classified `overlay` (an open dialog/overlay intercepts the interaction), the engine SHALL identify a dismiss control (deterministic heuristics first; LLM selection only among verified candidate controls), dismiss the overlay, verify it is gone, and rerun the keyword.

#### Scenario: Cookie banner blocks a click
- **WHEN** a click fails because an open dialog element intercepts the pointer
- **THEN** the engine dismisses the dialog, verifies no open dialog remains, and reruns the original keyword

#### Scenario: Dismissal fails safely
- **WHEN** no dismiss control can be verified within budget
- **THEN** the transaction ends unhealed with an RCA record naming the blocking overlay

### Requirement: Recovery actions are recorded
Every recovery action (wait duration, swipe count, dismissed control) SHALL be recorded in the heal event for reporting.

#### Scenario: Wait recovery appears in report
- **WHEN** a timing recovery heals a keyword after waiting 12 seconds
- **THEN** the heal event records the recovery type and measured wait duration

