# tiered-locator-selection

## ADDED Requirements

### Requirement: Tiered pipeline order
Locator healing SHALL attempt, in order: (1) deterministic candidate generation with fuzzy ranking against the failed locator, (2) LLM selection of one candidate index from the top-K ranked candidates with element info, (3) generation mode (full DOM prompt) as fallback when no candidates exist, the generator missed the element, or selection exhausts its retries. The active mode SHALL be configurable (`HEAL_LOCATOR_TIERS=selection|generation`).

#### Scenario: Common case heals via selection
- **WHEN** the deterministic generator produces candidates including the intended element
- **THEN** healing completes via an index-pick prompt containing candidates and element info, without sending the page DOM

#### Scenario: Generator miss falls back to generation
- **WHEN** no deterministic candidate resolves to a verifiable target
- **THEN** the pipeline falls back to generation mode with the DOM excerpt

### Requirement: Ranking never decides alone
Fuzzy-ranking confidence SHALL only order candidates; a heal SHALL NOT be applied from ranking alone without LLM selection, regardless of score or margin.

#### Scenario: High-confidence fuzzy match still confirmed
- **WHEN** the top-ranked candidate scores far above the rest
- **THEN** the LLM selection step still runs before any rerun

### Requirement: Selection output is verified like any proposal
The selected candidate SHALL pass the existing live verification (exists, unique, visible, type-compatible, option-content for selects) before rerun; rejected selections SHALL be retried with per-candidate feedback within the transaction budget.

#### Scenario: Wrong-type selection bounced
- **WHEN** the model selects a candidate whose element type is incompatible with the keyword
- **THEN** the validator rejects it with the tag-mismatch reason and the model picks again

### Requirement: Flat selection schema
The selection agent's output schema SHALL be flat (`index` integer plus optional reason) so it functions on prompted-JSON-only small models.

#### Scenario: 8B-class model heals via selection
- **WHEN** the locator role is served by a small model without reliable tool calling
- **THEN** selection-mode healing functions via prompted output
