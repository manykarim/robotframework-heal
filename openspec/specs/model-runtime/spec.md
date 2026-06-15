# model-runtime Specification

## Purpose
TBD - created by archiving change agentic-heal-rewrite. Update Purpose after archive.
## Requirements
### Requirement: Per-role model configuration
The runtime SHALL support independent model configuration per agent role (`triage`, `locator`, `vision`, `rca`) via `HEAL_*` settings (pydantic-settings), each accepting any OpenAI-compatible endpoint (`base_url` + key) or a pydantic-ai provider string; unset roles SHALL fall back to a default model setting.

#### Scenario: Mixed deployment
- **WHEN** `HEAL_LOCATOR_MODEL` points at a self-hosted vLLM endpoint and `HEAL_VISION_MODEL` at a hosted vision model
- **THEN** each agent uses its configured backend within one run

### Requirement: Capability profile and output-mode ladder
The runtime SHALL resolve a capability profile per role (`tools`, `structured_output`, `vision`, `context_budget`) from pydantic-ai model profiles plus user overrides, and `build_agent(role, schema)` SHALL wrap ANY output schema in the resolved output mode (native / tool / prompted) generically.

#### Scenario: vLLM strict-mode rejection avoided
- **WHEN** a role resolves to a backend that rejects strict tool definitions
- **THEN** tool schemas are sent without `strict`/`additionalProperties` and requests succeed

#### Scenario: Toolless model uses prompted output
- **WHEN** a role's profile resolves `structured_output: prompted`
- **THEN** structured outputs for any schema are obtained via prompted JSON with schema-derived instructions, including on models that emit `<think>` blocks

### Requirement: Budgets and usage ledger
The runtime SHALL enforce per-transaction usage limits and a run-level ledger with configurable caps (tokens, wall-clock per failure); cap breaches SHALL degrade behavior (skip healing, RCA-only) rather than abort the test run, and every heal event SHALL record tokens used, model, and output mode.

#### Scenario: Per-failure time cap
- **WHEN** a healing transaction exceeds `HEAL_MAX_FAILURE_SECONDS`
- **THEN** the transaction finalizes as unhealed with an RCA record and the run continues

### Requirement: Endpoint probing (doctor)
The runtime SHALL provide a probe that fires minimal calls at each configured endpoint to test tool calling, strict schemas, JSON output, and vision support, reporting a resolved capability profile and actionable misconfiguration errors (e.g., base_url path issues).

#### Scenario: Doctor identifies missing tool support
- **WHEN** the probe's tool-call test fails on the configured locator model
- **THEN** the doctor output recommends `prompted` output mode for that role

### Requirement: Offline testability
All agents SHALL be constructible with pydantic-ai test models so that engine logic, validators, and plugins run in CI without network access.

#### Scenario: CI run without LLM
- **WHEN** the unit test suite runs with `TestModel`
- **THEN** triage, locator, and RCA pipelines execute deterministically without HTTP calls

