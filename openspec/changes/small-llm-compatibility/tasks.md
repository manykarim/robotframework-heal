# Tasks: small-llm-compatibility

Experiments-first: the sweep (phase 2) runs before fixes (phase 3); fixes are driven by recorded findings, then re-measured (phase 4). Ollama host: `192.168.1.15:11434` (configurable).

## 1. Sweep harness

- [x] 1.1 Probed the host (18 models in inventory.json) and pinned the curated selection (models.py): 10 models across tiny/no-tools, 8B/tool-capable, larger-small, vision; 3 smoke models
- [x] 1.2 `sweep.py`: per-model doctor probe + corpus replay (element-identity grading), accuracy/latency/tokens/failure-modes, host-configurable, skips unreachable, writes results.json — smoke-validated
- [x] 1.3 `smoke.py`: live-browser heal of the bundled locator-drift suite for 3 representative models (full listener path through Ollama)

## 2. Run the sweep (baseline)

- [x] 2.1 **[EXPERIMENT]** Swept 9 models (vision deprecated on host); results.json captured (host dropped twice under load, resumed)
- [x] 2.2 FINDINGS.md: full matrix + issues classified. Headline: no engine bug — model quality is the differentiator; granite3.2:8b/gemma3:12b 92%, gemma3:4B 83%. Prompted floor validated (Ollama tool-calling unreliable)

## 3. Engine fixes (driven by findings)

- [ ] 3.1 Ollama backend preset in `runtime.py` (endpoint detection, prompted floor default, unreliable-tools-until-probed, vision per model) + unit tests
- [ ] 3.2 Per-model tool-support resolution honouring the `heal doctor` probe (don't pin a tool-capable Ollama model to prompted); strip Ollama-unsupported params; unit tests with `TestModel`/`FunctionModel`
- [ ] 3.3 Output-quirk tolerance in the prompted path for any quirks the sweep found (`<think>`, fenced JSON, trailing prose) as pre-parse normalisation only — verification unchanged; unit tests incl. a "normalised-but-wrong still fails verification" case
- [ ] 3.4 Any other clear engine bugs the sweep surfaced (scoped from findings)

## 4. Re-measure and report

- [ ] 4.1 **[EXPERIMENT]** Re-run the sweep after fixes; add before/after rows to the matrix; confirm no regression on the existing reference backends (MiniMax / OpenRouter)
- [ ] 4.2 Finalise `FINDINGS.md`: before/after deltas, recommended small-model settings, and any remaining model-limit caveats
- [ ] 4.3 Docs: add an Ollama setup entry to the model-providers how-to (`HEAL_BASE_URL=http://host:11434/v1`) and the small-model compatibility matrix to the docs benchmarks; note `heal doctor` as the way to resolve per-model capability
