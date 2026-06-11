# assertion-healing

## ADDED Requirements

### Requirement: Assertion-drift analysis
WHEN a failure is classified `assertion-drift` (expected/actual value mismatch in a verification keyword) and assertion healing is enabled (`HEAL_ASSERTIONS=true`), the engine SHALL compare the asserted expectation against the live page (text/vision evidence) and produce a typed adjustment proposal (keyword + corrected arguments) with confidence.

#### Scenario: UI text changed
- **WHEN** `Get Text` asserts "Save" but the live element reads "Save changes"
- **THEN** the proposal contains the corrected expected value, the evidence excerpt, and a confidence level

### Requirement: Adjustments are verified before passing
An assertion adjustment SHALL be applied only by rerunning the verification keyword with corrected arguments; the keyword result SHALL be PASS only if the rerun succeeds, and the heal event SHALL mark the assertion as drifted (not as originally passing).

#### Scenario: Corrected assertion passes
- **WHEN** the rerun with the corrected expected value succeeds
- **THEN** the keyword is marked PASS, and the heal event records original expectation, corrected expectation, and evidence

#### Scenario: Disabled by default
- **WHEN** `HEAL_ASSERTIONS` is not enabled
- **THEN** assertion failures produce RCA records only and the keyword remains FAIL

### Requirement: Numeric and semantic drift guard
The engine SHALL NOT propose adjustments that change the semantic target of the assertion (different element, different quantity scale) and SHALL flag such cases as `unknown` with RCA-only output.

#### Scenario: Value differs by magnitude
- **WHEN** the assertion expects "5 items" and the page shows "500 items"
- **THEN** no adjustment is proposed; the RCA record highlights the discrepancy as a likely application defect
