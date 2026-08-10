"""Curated model selection for the Ollama small-model healing sweep.

Chosen from the live inventory (experiments/ollama-small-models/inventory.json,
18 models on 192.168.1.15) to cover the capability axes: size (3.2B -> 14.8B),
tool-calling vs not, and vision. Coding/duplicate models are excluded as noise.

`expects_tools` is the prior expectation only — `heal doctor` probes the truth
at sweep time and the engine trusts the probe.
"""

OLLAMA_HOST = "192.168.1.15:11434"
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}/v1"

# (model, bucket, expects_tools, vision)
SELECTION = [
    ("llama3.2:latest",        "tiny/no-tools",   False, False),  # 3.2B
    ("phi3:latest",            "tiny/no-tools",   False, False),  # 3.8B
    ("phi4-mini:latest",       "tiny/no-tools",   False, False),  # 3.8B
    ("gemma3:latest",          "tiny/no-tools",   False, False),  # 4.3B
    ("llama3.1:latest",        "8B/tool-capable", True,  False),  # 8.0B
    ("qwen3:8b",               "8B/tool-capable", True,  False),  # 8.2B
    ("granite3.2:8b",          "8B/tool-capable", True,  False),  # 8.2B
    ("gemma3:12b",             "larger-small",    False, False),  # 12.2B
    ("qwen3:14b",              "larger-small",    True,  False),  # 14.8B
    ("llama3.2-vision:latest", "vision",          False, True),   # 9.8B
]

# models for the live-browser smoke (full listener path), representative of buckets
SMOKE_MODELS = ["llama3.2:latest", "llama3.1:latest", "qwen3:8b"]
