# model-runtime (delta)

## ADDED Requirements

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
