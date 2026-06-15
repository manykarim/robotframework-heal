# fix-engine Specification

## Purpose
TBD - created by archiving change agentic-heal-rewrite. Update Purpose after archive.
## Requirements
### Requirement: AST-based fix synthesis
Fix proposals for `.robot`/`.resource` files SHALL be synthesized via Robot Framework's parsing model (AST transformers), never via regex/string replacement, resolving the locator origin: literal argument, `prefix${VAR}suffix` argument shapes (single variable, with the variable definition updated when its value portion changed), variable definition in the same file or an imported `.resource` file, or a user-keyword argument traced one hop to its call sites.

#### Scenario: Literal locator in a test file
- **WHEN** a healed locator originated as a literal argument in a test case
- **THEN** the proposal replaces exactly that token in that test's keyword call

#### Scenario: Variable plus suffix argument
- **WHEN** the failing argument was `${MAIN_SELECTOR} img` and the variable's portion changed
- **THEN** the proposal updates the variable definition (including in imported `.resource` files) and preserves the argument structure

#### Scenario: Prefixed variable argument
- **WHEN** the failing argument was `css=${BTN_ID}` and the healed locator keeps the `css=` prefix
- **THEN** the proposal updates the `${BTN_ID}` variable definition rather than replacing the call-site token

#### Scenario: Locator passed into a user keyword
- **WHEN** the failing keyword call's locator is an argument of the enclosing user keyword and a test calls that keyword passing the broken literal
- **THEN** the proposal fixes the literal at the calling site (in the healed copies), not inside the keyword body

#### Scenario: Caller passes a variable
- **WHEN** the matching call site passes `${LOGIN_BTN}` whose definition equals the failed locator
- **THEN** the proposal updates that variable's definition

#### Scenario: No call site matches
- **WHEN** no call site's argument resolves to the failed locator
- **THEN** the fix is reported `unresolved` and no file content is changed

### Requirement: Blast-radius classification
Every fix proposal SHALL carry a blast radius: `local` (single call site) or `shared` (variable/keyword used at N sites, with the usage list); `shared` proposals SHALL NOT be auto-applied in-place.

#### Scenario: Shared variable demoted to review
- **WHEN** the fix changes a variable used in 14 keyword calls
- **THEN** the proposal is marked `shared`, lists all 14 usages, and is emitted as patch/delegated only

### Requirement: Tiered application
The fix engine SHALL always synthesize healed file copies and visual diffs as read-only report artifacts when fix proposals exist — original suites and resources are NEVER modified by report generation. `HEAL_FIX_TIER` SHALL gate only working-tree-facing outputs: Tier patch additionally emits a unified `.patch` aggregating all proposals; Tier in-place additionally edits source files at end-of-run, refused when the git working tree is dirty; structured handoff to a coding agent remains available via MCP/CLI.

#### Scenario: Copies and diffs by default
- **WHEN** a run heals a locator with default settings (`HEAL_FIX_TIER=report`)
- **THEN** healed copies appear under the report directory and the original files are byte-identical to before the run

#### Scenario: Patch artifact is git-appliable
- **WHEN** a run produces fix proposals at tier `patch`
- **THEN** `git apply <patch>` on a clean checkout applies all `local` fixes successfully

#### Scenario: In-place refused on dirty tree
- **WHEN** tier `in-place` is enabled and the working tree has uncommitted changes to a target file
- **THEN** no in-place edit occurs and the report explains why, with the patch still produced

### Requirement: Idempotent and verifiable rewrites
Applying the same proposal twice SHALL be a no-op; every rewritten file SHALL re-parse successfully with the Robot Framework parser before being written.

#### Scenario: Healed file remains valid RF syntax
- **WHEN** any fix is applied to a file
- **THEN** the resulting file parses without errors and non-target lines are byte-identical

