# Configure a model provider

heal works with any OpenAI-compatible endpoint or a pydantic-ai provider string.
Set the defaults once; every agent role (`triage`, `locator`, `vision`, `rca`)
inherits them and can be overridden individually. Always confirm with
`heal doctor` — capability is **probed, not assumed**.

!!! tip "Per-role overrides"
    Use a cheap fast model for triage and a stronger one for RCA, for example:
    `HEAL_TRIAGE_MODEL=openai/gpt-4.1-nano` and `HEAL_RCA_MODEL=openai/gpt-4.1`.
    See the [configuration reference](../reference/configuration.md).

=== "OpenAI / Azure"

    ```bash
    HEAL_MODEL=openai:gpt-4.1-mini      # pydantic-ai provider string
    HEAL_API_KEY=sk-...
    # Azure: set HEAL_BASE_URL to your Azure OpenAI endpoint
    ```

=== "OpenRouter"

    ```bash
    HEAL_MODEL=openai/gpt-4.1-nano
    HEAL_BASE_URL=https://openrouter.ai/api/v1
    HEAL_API_KEY=sk-or-...
    ```

=== "MiniMax"

    ```bash
    HEAL_MODEL=MiniMax-M2.5
    HEAL_BASE_URL=https://api.minimax.io/v1
    HEAL_API_KEY=...
    ```

    MiniMax's quirks (forced `tool_choice`) are handled by a built-in profile —
    heal resolves it to prompted output automatically.

=== "vLLM (self-hosted)"

    ```bash
    HEAL_MODEL=your-served-model
    HEAL_BASE_URL=http://your-vllm-host:8000/v1
    HEAL_API_KEY=token-abc          # if your gateway requires one
    ```

    Strict tool schemas (which vLLM rejects) are stripped automatically.

=== "Ollama (local)"

    ```bash
    HEAL_MODEL=qwen2.5
    HEAL_BASE_URL=http://localhost:11434/v1
    HEAL_API_KEY=ollama
    ```

=== "LiteLLM proxy"

    ```bash
    HEAL_MODEL=your-alias
    HEAL_BASE_URL=http://your-litellm-proxy:4000
    HEAL_API_KEY=sk-...
    ```

## Verify the endpoint

```bash
heal doctor --role all
```

`doctor` probes tool calling, JSON-schema output, prompted output, and vision,
then prints the resolved capabilities and the output mode it will use. If a
backend can only do prompted JSON, heal still heals — verification lives in
output validators, which work in every mode. See
[Capability-tiered models](../explanation/model-tiers.md) for why this matters
and how small models compare.
