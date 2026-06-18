"""Live-browser smoke: confirm the full RF listener path heals through Ollama.

Runs the bundled heal_locator_drift suite (local page, real Chromium) for a few
representative models. Temporarily points the project .env at Ollama per model
(the listener auto-loads .env), then restores it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from models import OLLAMA_BASE_URL, SMOKE_MODELS  # noqa: E402

ENV = ROOT / ".env"
SUITE = ROOT / "tests" / "atest" / "heal" / "heal_locator_drift.robot"


def _write_env(model: str) -> str:
    original = ENV.read_text() if ENV.exists() else ""
    env = original
    for key, val in (("HEAL_MODEL", model), ("HEAL_BASE_URL", OLLAMA_BASE_URL), ("HEAL_API_KEY", "ollama")):
        if re.search(rf"^{key}=", env, re.M):
            env = re.sub(rf"^{key}=.*$", f"{key}={val}", env, flags=re.M)
        else:
            env += f"\n{key}={val}\n"
    ENV.write_text(env)
    return original


def main():
    results = []
    for model in SMOKE_MODELS:
        original = _write_env(model)
        try:
            out = subprocess.run(
                ["uv", "run", "robot", "-d", f"/tmp/ollama-smoke/{model.replace(':', '_')}", str(SUITE)],
                cwd=ROOT, capture_output=True, text=True, timeout=600,
            )
            tail = out.stdout.splitlines()[-4:]
            passed = "0 failed" in out.stdout
            results.append((model, "PASS" if passed else "FAIL", " | ".join(t.strip() for t in tail if t.strip())[:120]))
        except subprocess.TimeoutExpired:
            results.append((model, "TIMEOUT", "exceeded 600s"))
        finally:
            ENV.write_text(original)
        print(f"{model:24} {results[-1][1]}", flush=True)
    print("\n=== smoke summary ===")
    for m, status, note in results:
        print(f"{m:24} {status:8} {note}")


if __name__ == "__main__":
    main()
