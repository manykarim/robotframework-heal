# eval-corpus Specification

## Purpose
TBD - created by archiving change tiered-healing-and-frames. Update Purpose after archive.
## Requirements
### Requirement: Corpus harvesting from run stores
A `heal corpus` CLI command SHALL extract ground-truth eval cases (healed events whose verified locator uniquely resolves in the recorded DOM evidence) from one or more run stores into the eval fixture set, deduplicated by failed locator, healed locator and DOM content hash.

#### Scenario: Harvest after a test run
- **WHEN** `heal corpus harvest results/` runs after executions with heal events
- **THEN** new unique fixtures appear in the eval fixture directory and re-harvesting the same stores adds nothing

### Requirement: Evals discover the corpus
The replay eval runner SHALL discover all harvested fixtures dynamically and report per-fixture and aggregate accuracy for the configured backend and tier mode.

#### Scenario: Tier change validated against the corpus
- **WHEN** the eval runner executes with `HEAL_LOCATOR_TIERS=selection` and a configured model
- **THEN** it replays every fixture offline and reports selection-tier accuracy against the recorded ground truth

