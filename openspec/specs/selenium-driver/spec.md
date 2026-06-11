# selenium-driver Specification

## Purpose
TBD - created by archiving change tiered-healing-and-frames. Update Purpose after archive.
## Requirements
### Requirement: SessionDriver for SeleniumLibrary
The package SHALL provide a SeleniumLibrary `SessionDriver` (query: count/visibility/viewport; inspect: page source, simplified DOM, element info, ready state, dialog detection, form issues, screenshot; act: scroll into view, click, fill, wait-until-ready), registered with the listener for failures owned by SeleniumLibrary.

#### Scenario: Selenium locator drift healed
- **WHEN** a SeleniumLibrary keyword fails with a broken locator
- **THEN** the engine diagnoses and heals it through the tiered pipeline with locators in SeleniumLibrary syntax (`css:`/`xpath:` prefixes)

#### Scenario: Timing and overlay recovery on Selenium
- **WHEN** a SeleniumLibrary keyword fails while the document is loading or blocked by an open dialog
- **THEN** the timing/overlay plugins recover using the Selenium driver primitives

### Requirement: Selenium frame limitation is explicit
Frame-pierced healing SHALL NOT be attempted for SeleniumLibrary (no pierce syntax); failures whose target appears to live in a frame SHALL produce an RCA naming the frame limitation.

#### Scenario: Frame target on Selenium degrades to RCA
- **WHEN** a Selenium keyword's intended element is inside an iframe
- **THEN** the transaction ends unhealed with an RCA explaining frame context is required

### Requirement: Optional dependency
SeleniumLibrary support SHALL be packaged as an optional extra; environments without it SHALL be unaffected.

#### Scenario: No selenium installed
- **WHEN** SeleniumLibrary is not installed
- **THEN** the listener registers no Selenium driver and other libraries heal normally

