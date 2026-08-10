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

### Requirement: Ollama backend support
The runtime SHALL recognise an Ollama OpenAI-compatible endpoint (by its default port) and resolve a safe default capability profile for it: structured output via the prompted floor and tool support treated as unreliable, because the sweep found tool calling unavailable or unreliable over Ollama's OpenAI-compatible endpoint for ~all models. A model that probes reliably tool-capable MAY still be upgraded via the doctor override mechanism.

#### Scenario: Ollama endpoint resolves to the prompted floor
- **WHEN** a role is configured with an Ollama base URL and a model
- **THEN** the resolved capability uses prompted structured output with tool support unreliable

#### Scenario: Probe override can upgrade a tool-capable model
- **WHEN** a probed-reliable capability is installed for an Ollama role via `override_capabilities`
- **THEN** the resolved capability uses that mode rather than the prompted default

> **De-scoped (evidence):** the proposal anticipated a "small-model output-quirk
> tolerance" requirement (`<think>`/fenced-JSON normalisation). The Ollama sweep
> did not support it — the framework's prompted path already tolerates reasoning
> blocks (qwen3 healed at 83% on 8B; it emits clean JSON on simple prompts), and
> no parse-error bottleneck was observed. Model failures were timeouts or
> verification rejections (model-quality), not parse bugs. No such requirement is
> added. See `experiments/ollama-small-models/FINDINGS.md`.

### Requirement: Output-mode safety rule
Before healing with a resolved structured-output mode, the runtime SHALL verify that the configured model can produce it, and SHALL fall back to a probed-working mode when it cannot. A mode that passes its probe SHALL NOT be overridden, because a probe establishes whether a transport works and not whether it heals better: `gemma-3-4b` passes both the native and prompted probes yet heals 75% prompted against 35% native, and MiniMax probes tool-capable yet is deliberately pinned to prompted on separate evidence. The verification SHALL cost at most one probe call per endpoint in the common case, SHALL be cached per endpoint for the run so roles sharing a model are probed once, SHALL run outside the per-failure time budget, and SHALL be disableable by configuration. A correction SHALL be surfaced to the user rather than applied silently.

#### Scenario: Broken configured mode falls back to one that works
- **WHEN** the resolved output mode fails its probe and another mode passes
- **THEN** healing uses the passing mode, and the correction is reported

#### Scenario: Working mode is never second-guessed
- **WHEN** the resolved output mode passes its probe
- **THEN** healing uses it, even if another mode also passes

#### Scenario: Probing is skipped when disabled
- **WHEN** capability probing is disabled by configuration
- **THEN** no probe call is made and the resolved mode is used unchanged

#### Scenario: Unprobeable endpoint keeps the configured mode
- **WHEN** no mode can be probed successfully
- **THEN** the configured mode is used unchanged rather than healing being blocked

