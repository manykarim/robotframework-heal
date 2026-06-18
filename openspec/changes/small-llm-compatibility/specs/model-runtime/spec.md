# model-runtime (delta)

## ADDED Requirements

### Requirement: Ollama backend support
The runtime SHALL recognise an Ollama OpenAI-compatible endpoint and resolve a safe default capability profile for it (structured output via the prompted floor, tool support treated as unreliable until probed, vision per model). Ollama-unsupported request parameters SHALL be stripped so requests succeed.

#### Scenario: Ollama endpoint resolves to a working default
- **WHEN** a role is configured with an Ollama base URL and a model
- **THEN** healing functions using the prompted output floor without sending parameters the endpoint rejects

#### Scenario: Probe upgrades a tool-capable Ollama model
- **WHEN** `heal doctor` probes an Ollama model that reliably tool-calls
- **THEN** the resolved capability for that role uses tool output rather than being pinned to prompted

### Requirement: Small-model output-quirk tolerance
The prompted structured-output path SHALL tolerate common small-model output quirks — reasoning/`<think>` blocks, markdown-fenced JSON, and surrounding prose — by normalising the response before validation. This normalisation SHALL NOT relax the output schema or the live verification: a parseable but semantically wrong proposal SHALL still fail verification.

#### Scenario: Fenced or think-wrapped JSON still parses
- **WHEN** a small model returns the required JSON wrapped in a code fence or after a `<think>` block
- **THEN** the structured output is extracted and validated successfully

#### Scenario: Tolerance does not weaken verification
- **WHEN** a normalised response yields a locator that fails live verification
- **THEN** the proposal is rejected and retried, exactly as for any other model
