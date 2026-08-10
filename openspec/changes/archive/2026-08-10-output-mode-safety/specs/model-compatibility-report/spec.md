# model-compatibility-report (delta)

## MODIFIED Requirements

### Requirement: Verification integrity under sweep
The sweep SHALL NOT relax healing verification: a proposal that fails live (replayed) verification SHALL be counted as not-healed. Verification establishes that a locator resolves to exactly one element, that the element is visible, and that the keyword reruns successfully — **none of which is semantic**, so a heal that satisfies all three MAY still target the wrong element. Correctness SHALL therefore be decided by element-identity grading against recorded ground truth, not by verification alone, and the report SHALL NOT claim that verification prevents plausible-but-wrong heals.

#### Scenario: Wrong proposal counts as not healed
- **WHEN** a proposal resolves to no element, or to more than one, or the keyword fails to rerun with it
- **THEN** live verification rejects it and the sweep records that fixture as not healed

#### Scenario: Wrong element counts as not correct
- **WHEN** a model proposes a locator that resolves uniquely to an element that is not the recorded ground truth
- **THEN** element-identity grading records that fixture as not correct for that model, even though the engine reported a successful heal

## ADDED Requirements

### Requirement: Wrong-element heals are reported
The report SHALL count, per model, the heals that the engine reported as successful but that element-identity grading rejected, and SHALL surface that count alongside accuracy. Accuracy alone understates risk: a model that heals to the wrong element is more dangerous than one that refuses, because the failure is silent and the test still passes.

#### Scenario: Silent mis-heals are visible in the report
- **WHEN** a model heals fixtures to elements other than the recorded ground truth
- **THEN** the per-model record carries the count of those heals separately from accuracy
