# model-compatibility-report Specification

## Purpose
TBD - created by archiving change small-llm-compatibility. Update Purpose after archive.
## Requirements
### Requirement: Reproducible cross-model healing sweep
A sweep harness SHALL evaluate healing across a configurable list of models on a configurable OpenAI-compatible backend, recording for each model: reachability, the `heal doctor` capability resolution, the resolved output mode, healing accuracy graded by element identity against the eval corpus, median latency, median token usage, and any failure modes. The harness SHALL be host-configurable and SHALL skip a model that is unreachable rather than aborting the sweep.

#### Scenario: Sweep a model list against a backend
- **WHEN** the harness is run with a list of models and a backend base URL
- **THEN** it produces a per-model result record (capabilities, accuracy, latency, tokens, failures) for every reachable model

#### Scenario: Unreachable model is skipped, not fatal
- **WHEN** one model in the list cannot be reached or errors on every fixture
- **THEN** the sweep records that model as failed and continues with the rest

### Requirement: Structured compatibility report
The sweep SHALL emit a machine-readable results file and a written report containing a per-model matrix and an issues log that classifies each finding as an engine bug, a model-quality limit, or a configuration gotcha.

#### Scenario: Report distinguishes engine bugs from model limits
- **WHEN** the report is generated from a sweep
- **THEN** every recorded issue is classified as engine-bug, model-limit, or config-gotcha

#### Scenario: Results are reproducible without the host
- **WHEN** the committed results file and report are read on a machine without the Ollama host
- **THEN** the per-model matrix and issues are fully available

### Requirement: Verification integrity under sweep
The sweep SHALL NOT relax healing verification: a proposal that fails live (replayed) verification SHALL be counted as not-healed. Verification establishes that a locator resolves to exactly one element, that the element is visible, and that the keyword reruns successfully — **none of which is semantic**, so a heal that satisfies all three MAY still target the wrong element. Correctness SHALL therefore be decided by element-identity grading against recorded ground truth, not by verification alone, and the report SHALL NOT claim that verification prevents plausible-but-wrong heals.

#### Scenario: Wrong proposal counts as not healed
- **WHEN** a proposal resolves to no element, or to more than one, or the keyword fails to rerun with it
- **THEN** live verification rejects it and the sweep records that fixture as not healed

#### Scenario: Wrong element counts as not correct
- **WHEN** a model proposes a locator that resolves uniquely to an element that is not the recorded ground truth
- **THEN** element-identity grading records that fixture as not correct for that model, even though the engine reported a successful heal

### Requirement: Wrong-element heals are reported
The report SHALL count, per model, the heals that the engine reported as successful but that element-identity grading rejected, and SHALL surface that count alongside accuracy. Accuracy alone understates risk: a model that heals to the wrong element is more dangerous than one that refuses, because the failure is silent and the test still passes.

#### Scenario: Silent mis-heals are visible in the report
- **WHEN** a model heals fixtures to elements other than the recorded ground truth
- **THEN** the per-model record carries the count of those heals separately from accuracy

