"""Curated OpenRouter model set for the small-model healing sweep.

Chosen to mirror the Ollama fleet swept in ``experiments/ollama-small-models``
so the two matrices are broadly comparable, plus a frontier-tier reference row.

The mapping is *approximate* and the differences matter when reading results:
OpenRouter serves different weights/quantisations behind a different stack, and
two rows have no exact counterpart (noted below). Treat this as "the same model
families", not "the same models".
"""

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

#: (model id, bucket, ollama counterpart)
MODELS = [
    ("google/gemma-3-4b-it", "tiny", "gemma3:latest (4.3B)"),
    ("google/gemma-3-12b-it", "larger-small", "gemma3:12b"),
    ("meta-llama/llama-3.1-8b-instruct", "8B", "llama3.1:latest"),
    ("meta-llama/llama-3.2-3b-instruct", "tiny", "llama3.2:latest"),
    ("qwen/qwen3-8b", "8B/reasoning", "qwen3:8b"),
    ("qwen/qwen3-14b", "larger-small/reasoning", "qwen3:14b"),
    # phi-4 (14B), not the 3.8B phi4-mini that scored 8% on Ollama
    ("microsoft/phi-4", "larger-small", "phi4-mini (approx. only)"),
    # granite 4.1, a generation newer than the swept granite3.2:8b
    ("ibm-granite/granite-4.1-8b", "8B", "granite3.2:8b (approx. only)"),
    # reference tier: not a small model, included to anchor the scale
    ("openai/gpt-4.1-nano", "reference", "n/a"),
]
