# Tasks: small-llm-compatibility

Experiments-first: the sweep (phase 2) runs before fixes (phase 3); fixes are driven by recorded findings, then re-measured (phase 4). Ollama host: `192.168.1.15:11434` (configurable).

## 1. Sweep harness

- [ ] 1.1 Probe the Ollama host (`/api/tags`) and pin the curated model selection (tiny/no-tools, 8B/tool-capable, larger-small, vision) in the runner config; record the full model inventory
- [ ] 1.2 Implement `experiments/ollama-small-models/sweep.py`: for each model, build `HealSettings(model, base_url, api_key="ollama")`, run `heal doctor` (capabilities), then replay the eval corpus grading element identity; collect reachability, resolved output mode, accuracy %, median latency, median tokens, and per-fixture failure modes; host-configurable; skip unreachable models; write `results.json`
- [ ] 1.3 Add a small live-browser smoke step (bundled `heal_locator_drift` page) for 2–3 representative models to confirm the full listener path

## 2. Run the sweep (baseline)

- [ ] 2.1 **[EXPERIMENT]** Run the full sweep against the Ollama fleet (corpus + smokes); capture `results.json` and raw notes
- [ ] 2.2 Triage results into `experiments/ollama-small-models/FINDINGS.md`: per-model matrix + an issues log classifying each finding as engine-bug / model-limit / config-gotcha

## 3. Engine fixes (driven by findings)

- [ ] 3.1 Ollama backend preset in `runtime.py` (endpoint detection, prompted floor default, unreliable-tools-until-probed, vision per model) + unit tests
- [ ] 3.2 Per-model tool-support resolution honouring the `heal doctor` probe (don't pin a tool-capable Ollama model to prompted); strip Ollama-unsupported params; unit tests with `TestModel`/`FunctionModel`
- [ ] 3.3 Output-quirk tolerance in the prompted path for any quirks the sweep found (`<think>`, fenced JSON, trailing prose) as pre-parse normalisation only — verification unchanged; unit tests incl. a "normalised-but-wrong still fails verification" case
- [ ] 3.4 Any other clear engine bugs the sweep surfaced (scoped from findings)

## 4. Re-measure and report

- [ ] 4.1 **[EXPERIMENT]** Re-run the sweep after fixes; add before/after rows to the matrix; confirm no regression on the existing reference backends (MiniMax / OpenRouter)
- [ ] 4.2 Finalise `FINDINGS.md`: before/after deltas, recommended small-model settings, and any remaining model-limit caveats
- [ ] 4.3 Docs: add an Ollama setup entry to the model-providers how-to (`HEAL_BASE_URL=http://host:11434/v1`) and the small-model compatibility matrix to the docs benchmarks; note `heal doctor` as the way to resolve per-model capability
