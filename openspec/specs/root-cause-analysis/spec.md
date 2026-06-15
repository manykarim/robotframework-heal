# root-cause-analysis Specification

## Purpose
TBD - created by archiving change agentic-heal-rewrite. Update Purpose after archive.
## Requirements
### Requirement: RCA record for every failure
Every healing transaction — healed, unhealed, or suppressed-by-budget — SHALL produce a typed `RcaRecord` containing: failure class, a clean human-readable error message, evidence references (DOM excerpt, screenshots, console/network excerpts when collected), actions attempted, outcome, and a suggested permanent fix when one exists.

#### Scenario: Unhealable failure gets enriched error
- **WHEN** a locator cannot be healed within budget
- **THEN** the RCA record contains the original error, the candidates tried with their verification results, and a clean summary message

#### Scenario: Healed failure documents itself
- **WHEN** a locator is healed successfully
- **THEN** the RCA record explains what changed on the page and why the new locator was chosen

### Requirement: Test-change context from version control
WHEN the test source is inside a git repository, the engine SHALL collect the last-modified date and recent history of the failing line/file (bounded, cached per file) and the RCA agent SHALL use it to distinguish "test outdated" from "application changed" hypotheses.

#### Scenario: Old test, new app behavior
- **WHEN** the failing locator's line last changed 14 months ago
- **THEN** the RCA record notes the test's age as supporting evidence for application-side change

#### Scenario: No git repository
- **WHEN** the test source is not in a git repository
- **THEN** RCA proceeds without git evidence and does not error

### Requirement: Clean message replaces raw stack noise
The RCA clean message SHALL state what was attempted, what the keyword targeted, what the page actually contained, and the most likely root cause — without raw Playwright/Appium stack traces (which remain available as evidence references).

#### Scenario: Clean message in the log
- **WHEN** a transaction completes
- **THEN** the RF log contains the clean message and a link/reference to the full evidence in the report

