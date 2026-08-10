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

    Capability varies per model behind the one endpoint, so heal resolves the
    **prompted** floor by default, then verifies that mode works before healing
    with it and falls back if it does not — so a reasoning model like `qwen3-8b`,
    which cannot produce prompted JSON in time, is corrected to native
    automatically (0% → 100% on the corpus).

    Best measured picks: `ibm-granite/granite-4.1-8b` and `qwen/qwen3-14b` (95%
    in either mode). Avoid `meta-llama/llama-3.2-3b-instruct`, which healed to
    the *wrong* element in half its fixtures. One model needs a manual pin:
    `gemma-3-4b` scores **75% prompted against 35% native** while passing both
    probes, so nothing can detect it for you:

    ```bash
    HEAL_LOCATOR_OUTPUT_MODE=prompted   # only for gemma-3-4b-style outliers
    ```

    Full matrix: `experiments/small-model-sweep/FINDINGS.md`.

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
    HEAL_MODEL=gemma3                       # 4.3B — best quality/speed
    HEAL_BASE_URL=http://localhost:11434/v1 # or http://<host>:11434/v1
    HEAL_API_KEY=ollama                     # any placeholder; Ollama ignores it
    ```

    Ollama runs on the **prompted** floor — the same default every unknown
    OpenAI-compatible backend gets; the `:11434` preset makes it explicit
    rather than incidental. A sweep found Ollama's OpenAI-compatible endpoint
    does not reliably expose tool calling, and prompted JSON + validator-based
    verification heals well without it.

    **Recommended models:** `gemma3` (4.3B) for the best quality/speed,
    `granite3.2:8b` or `gemma3:12b` for the highest accuracy. Avoid heavy
    reasoning models (e.g. `qwen3:14b`) and very small ones (`phi4-mini`,
    `llama3.2`). These rankings come from locator-drift healing only — set
    `HEAL_TRIAGE_MODEL` / `HEAL_RCA_MODEL` separately if you want a different
    model for the other roles, since `HEAL_MODEL` configures all of them.
    Slow hardware may need a higher `HEAL_MAX_FAILURE_SECONDS`. See the
    [small-model matrix](../explanation/model-tiers.md#ollama-small-model-compatibility).

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
