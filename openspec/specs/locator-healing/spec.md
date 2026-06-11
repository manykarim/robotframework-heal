# locator-healing Specification

## Purpose
TBD - created by archiving change agentic-heal-rewrite. Update Purpose after archive.
## Requirements
### Requirement: Verified locator proposals
The locator agent SHALL return typed locator proposals, and every proposal SHALL be verified against the live session (element exists, is unique or uniquely resolvable, is visible, and is type-compatible with the keyword) before being used; verification failures SHALL be fed back to the agent as retry feedback.

#### Scenario: Invalid proposal is bounced back
- **WHEN** the agent proposes a locator matching 3 elements
- **THEN** the output validator raises a retry with the match count and the agent produces a corrected proposal

#### Scenario: No unverified locator reaches the test
- **WHEN** all proposals fail live verification within the retry budget
- **THEN** the transaction ends unhealed and an RCA record is produced; the keyword result remains FAIL

### Requirement: Keyword rerun with healed locator
After a verified proposal, the engine SHALL rerun the original keyword with the healed locator, preserve return-value assignment to the original variable, and set the keyword result to PASS only when the rerun succeeds.

#### Scenario: Successful heal passes the keyword
- **WHEN** the rerun with the healed locator succeeds
- **THEN** the keyword result status is PASS and any assigned variable receives the rerun's return value

### Requirement: Greedy reuse of known fixes
Within a run, the engine SHALL remember broken→healed locator mappings and SHALL substitute a known healed locator before keyword execution when the broken locator is used again and still matches 0 elements.

#### Scenario: Second occurrence healed without LLM
- **WHEN** a previously healed broken locator appears in a later keyword
- **THEN** the healed locator is substituted proactively without invoking the locator agent

### Requirement: Tool-tier-aware proposal generation
On models with reliable tool calling, the locator agent MAY use exploration tools (`query_dom`, `get_element_info`); on models without, the agent SHALL receive a curated simplified DOM excerpt and propose without tools. Verification SHALL function identically in both modes.

#### Scenario: Toolless model still heals with verification
- **WHEN** the configured locator model has `tools: none`
- **THEN** healing proceeds via prompted structured output with validator-based verification

