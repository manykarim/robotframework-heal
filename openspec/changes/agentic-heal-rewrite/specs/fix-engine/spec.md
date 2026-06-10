# fix-engine

## ADDED Requirements

### Requirement: AST-based fix synthesis
Fix proposals for `.robot`/`.resource` files SHALL be synthesized via Robot Framework's parsing model (AST transformers), never via regex/string replacement, resolving the locator origin: literal argument, user-keyword argument, variable definition in the same file, or variable definition in an imported resource file.

#### Scenario: Literal locator in a test file
- **WHEN** a healed locator originated as a literal argument in a test case
- **THEN** the proposal replaces exactly that token in that test's keyword call

#### Scenario: Variable plus suffix argument
- **WHEN** the failing argument was `${MAIN_SELECTOR} img` and the variable's portion changed
- **THEN** the proposal updates the variable definition (including in imported `.resource` files) and preserves the argument structure

### Requirement: Blast-radius classification
Every fix proposal SHALL carry a blast radius: `local` (single call site) or `shared` (variable/keyword used at N sites, with the usage list); `shared` proposals SHALL NOT be auto-applied in-place.

#### Scenario: Shared variable demoted to review
- **WHEN** the fix changes a variable used in 14 keyword calls
- **THEN** the proposal is marked `shared`, lists all 14 usages, and is emitted as patch/delegated only

### Requirement: Tiered application
The fix engine SHALL support: Tier 0 report-only (default), Tier 1 healed file copies plus a unified `.patch` aggregating all proposals, Tier 2 opt-in in-place editing executed only at end-of-run and refused when the git working tree is dirty, Tier 3 structured handoff of proposals to a coding agent (via MCP/CLI).

#### Scenario: Patch artifact is git-appliable
- **WHEN** a run produces fix proposals at Tier 1
- **THEN** `git apply <patch>` on a clean checkout applies all `local` fixes successfully

#### Scenario: In-place refused on dirty tree
- **WHEN** Tier 2 is enabled and the working tree has uncommitted changes to a target file
- **THEN** no in-place edit occurs and the report explains why, with the patch still produced

### Requirement: Idempotent and verifiable rewrites
Applying the same proposal twice SHALL be a no-op; every rewritten file SHALL re-parse successfully with the Robot Framework parser before being written.

#### Scenario: Healed file remains valid RF syntax
- **WHEN** any fix is applied to a file
- **THEN** the resulting file parses without errors and non-target lines are byte-identical
