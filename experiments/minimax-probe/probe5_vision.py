"""Probe 5: vision capability for healing duties (gates tasks 6.5/6.6).

Synthetic screenshots (cv2): a form with a visible required-field error and a
loading screen. Questions mirror what form-diagnosis and timing checks need.
Flat schemas, prompted output (the universal floor).
"""

import asyncio
import os
import time
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import PromptedOutput
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv(Path(__file__).parents[2] / ".env")


def make_form_error_png() -> bytes:
    img = np.full((400, 640, 3), 255, dtype=np.uint8)
    cv2.putText(img, "Checkout", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 2)
    cv2.putText(img, "Email *", (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 1)
    cv2.rectangle(img, (40, 125), (420, 165), (0, 0, 220), 2)  # red-bordered empty field
    cv2.putText(img, "Email is required", (40, 195), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 220), 1)
    cv2.putText(img, "Name", (40, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 1)
    cv2.rectangle(img, (40, 255), (420, 295), (120, 120, 120), 1)
    cv2.putText(img, "Jane Doe", (50, 282), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 60), 1)
    cv2.rectangle(img, (40, 330), (180, 370), (40, 140, 40), -1)
    cv2.putText(img, "Submit", (60, 357), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return cv2.imencode(".png", img)[1].tobytes()


def make_loading_png() -> bytes:
    img = np.full((400, 640, 3), 245, dtype=np.uint8)
    cv2.circle(img, (320, 180), 40, (180, 180, 180), 6)
    cv2.ellipse(img, (320, 180), (40, 40), 0, 0, 90, (60, 60, 200), 6)
    cv2.putText(img, "Loading...", (270, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (90, 90, 90), 2)
    return cv2.imencode(".png", img)[1].tobytes()


class LoadingVerdict(BaseModel):
    is_loading: str  # "true" / "false"
    reason: str


class FormVerdict(BaseModel):
    has_validation_error: str  # "true" / "false"
    error_fields: list[str]


BACKENDS = []
if os.environ.get("MINIMAX_API_KEY"):
    BACKENDS.append(
        ("MiniMax-M3", OpenAIProvider(base_url="https://api.minimax.io/v1", api_key=os.environ["MINIMAX_API_KEY"]))
    )
if os.environ.get("OPENROUTER_API_KEY"):
    orp = OpenAIProvider(base_url=os.environ["OPENROUTER_BASE_URL"], api_key=os.environ["OPENROUTER_API_KEY"])
    BACKENDS.append(("google/gemini-2.5-flash-lite", orp))
    BACKENDS.append(("openai/gpt-4.1-nano", orp))

results = []


async def probe(model_name, provider, schema, prompt, png, check):
    model = OpenAIChatModel(model_name, provider=provider)
    agent = Agent(model, output_type=PromptedOutput(schema), retries=2)
    t0 = time.time()
    try:
        res = await agent.run([prompt, BinaryContent(data=png, media_type="image/png")])
        ok = check(res.output)
        results.append((model_name, schema.__name__, "PASS" if ok else "QUAL", time.time() - t0, str(res.output)[:90]))
    except Exception as e:
        results.append((model_name, schema.__name__, "ERR", time.time() - t0, f"{type(e).__name__}: {e}"[:90]))
    print(results[-1], flush=True)


async def main():
    form_png, loading_png = make_form_error_png(), make_loading_png()
    for name, provider in BACKENDS:
        await probe(
            name, provider, LoadingVerdict,
            "Does this app screenshot show a loading state? is_loading true/false.",
            loading_png, lambda o: o.is_loading.lower() == "true",
        )
        await probe(
            name, provider, LoadingVerdict,
            "Does this app screenshot show a loading state? is_loading true/false.",
            form_png, lambda o: o.is_loading.lower() == "false",
        )
        await probe(
            name, provider, FormVerdict,
            "Does this form screenshot show a field validation error? Which fields?",
            form_png, lambda o: o.has_validation_error.lower() == "true" and any("mail" in f.lower() for f in o.error_fields),
        )
    print("\n=== SUMMARY ===", flush=True)
    for r in results:
        print(f"{r[2]:4} {r[3]:5.1f}s {r[0]:34} {r[1]:14} {r[4]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
