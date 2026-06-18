# model-compatibility-report

## ADDED Requirements

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
The sweep SHALL NOT relax healing verification: a proposal that does not pass live (replayed) verification SHALL be counted as not-healed, so the report can never record a plausible-but-wrong locator as a successful heal.

#### Scenario: Wrong proposal counts as not healed
- **WHEN** a model proposes a locator that resolves to the wrong element in a fixture
- **THEN** the sweep records that fixture as not healed for that model
