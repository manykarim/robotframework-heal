# form-diagnosis Specification

## Purpose
TBD - created by archiving change agentic-heal-rewrite. Update Purpose after archive.
## Requirements
### Requirement: Mandatory-field diagnosis on form failures
WHEN a failure is classified `form-state` (a submit/continue action fails or is blocked while the page contains required or invalid fields), the engine SHALL produce a diagnosis listing the unfilled required fields and visible validation errors, derived from DOM analysis (required/aria-required/aria-invalid attributes, validation message elements) and, when a vision-capable model is configured, screenshot analysis.

#### Scenario: Submit blocked by empty required field
- **WHEN** a click on a submit control fails and the form contains `<input required>` elements without values
- **THEN** the RCA record lists each unfilled required field with its label/locator and states that the test never filled them

#### Scenario: DOM-only fallback without vision model
- **WHEN** no vision-capable model is configured
- **THEN** form diagnosis still runs using DOM evidence only and the report labels the diagnosis as DOM-only

### Requirement: Diagnose-only by default
Form diagnosis SHALL NOT enter values into fields unless explicit opt-in (`HEAL_FORM_FILL=true`) is configured; with opt-in, filled values SHALL be recorded in the heal event and the fix proposal SHALL be a test-code change, not silent data invention.

#### Scenario: Default posture does not modify the form
- **WHEN** form-state is diagnosed with default configuration
- **THEN** no fill/select actions are performed on the page and the keyword remains FAIL with an enriched error

