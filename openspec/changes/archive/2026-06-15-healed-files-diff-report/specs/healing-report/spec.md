# healing-report (delta)

## ADDED Requirements

### Requirement: Visual diff report
Report generation SHALL render a self-contained side-by-side HTML diff for every file with synthesized fixes: line numbers on both sides, intra-line highlighting of changed words within modified lines, unchanged-context folding, and a per-file header summarizing the applied locator mappings with their blast radii; a diff index SHALL list all changed files. The dashboard SHALL link each fix proposal to its diff page and embed the changed lines inline in the transaction drill-down.

#### Scenario: Reviewer sees exactly what changed
- **WHEN** a run heals a locator that lives in a `.resource` variable
- **THEN** the diff page shows the variable definition line side-by-side with the old and new value word-highlighted, and unchanged regions folded

#### Scenario: Diff is reachable from the proposal
- **WHEN** the dashboard lists a fix proposal
- **THEN** it links to the corresponding file diff and shows the changed lines inline

#### Scenario: Self-contained artifact
- **WHEN** a diff page is opened from a CI artifact download without network access
- **THEN** it renders fully (no external scripts, styles, or fonts)
