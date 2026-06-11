# heal-cli

## ADDED Requirements

### Requirement: CLI entry point
The package SHALL install a `heal` console script with subcommands: `triage` (post-run analysis of an RF output directory / output.xml plus run store), `report` (render dashboard/summary from a store), `apply` (apply fix proposals by tier), `mcp` (start the MCP server), `doctor` (probe configured model endpoints).

#### Scenario: Post-run triage without a live browser
- **WHEN** `heal triage <outputdir>` runs after a test execution
- **THEN** failures recorded in the store are summarized with diagnoses and fix proposals, without starting a browser

#### Scenario: Apply respects safety tiers
- **WHEN** `heal apply --in-place` runs with a dirty git working tree
- **THEN** the command refuses, explains, and offers `--patch` output instead

#### Scenario: Doctor diagnoses an endpoint
- **WHEN** `heal doctor` runs with a configured model endpoint
- **THEN** it reports per-role capability resolution (tools / structured output / vision) and actionable errors for failed probes

### Requirement: Configuration transparency
`heal doctor` and `heal report` SHALL print the resolved configuration (models per role, output modes, budgets, report paths) with secrets redacted.

#### Scenario: Redacted output
- **WHEN** any CLI command prints configuration
- **THEN** API keys are masked
