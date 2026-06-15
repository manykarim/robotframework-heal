# heal-memory Specification

## Purpose
TBD - created by archiving change tiered-healing-and-frames. Update Purpose after archive.
## Requirements
### Requirement: Warm start from healing history
WHEN warm start is enabled (`HEAL_WARM_START`, default true) and a healing history database exists, the listener SHALL load recent healed locator mappings (scoped by source file, bounded age and count) into the greedy-reuse map before the first qualifying failure.

#### Scenario: Fix from a previous run applied proactively
- **WHEN** a locator healed in a previous run is used again and still matches 0 elements while its healed form matches
- **THEN** the locator is swapped before keyword execution, avoiding the keyword timeout and any LLM call

### Requirement: Staleness guard
A warm-started mapping SHALL only be applied when the broken locator currently matches 0 elements and the healed locator currently matches at least 1; mappings failing this check SHALL be ignored for that use without disabling normal healing.

#### Scenario: Outdated mapping falls through
- **WHEN** the app changed so the recorded healed locator no longer matches
- **THEN** the keyword runs with its original locator and normal healing handles the failure

### Requirement: Warm-start provenance
Heals applied via warm start SHALL be recorded as events with warm-start provenance so reports distinguish them from fresh heals.

#### Scenario: Dashboard shows warm-start origin
- **WHEN** a warm-started swap fixes a keyword
- **THEN** the run report shows the event marked as reused-from-history

