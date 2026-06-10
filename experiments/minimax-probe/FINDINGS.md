# Findings: structured-output & tool-calling capability probes

**Date**: 2026-06-10 · **pydantic-ai**: 1.107.0 · **Backends**: MiniMax (`https://api.minimax.io/v1`, OpenAI-compatible), OpenRouter (small/cheap models)

Gates design decision **D5 (capability-tiered model runtime)** in `openspec/changes/agentic-heal-rewrite/design.md` and task 2.2 in `tasks.md`.

## Probe 1 — MiniMax-M2.5, pydantic-ai defaults (`probe.py`)

| Probe | What it validates | Result | Time | Note |
|---|---|---|---|---|
| P1 ToolOutput | structured output via tool call (pydantic-ai default) | **FAIL** | 14.5s | `UnexpectedModelBehavior: Exceeded maximum output retries` |
| P2 NativeOutput | `response_format: json_schema` | **PASS** | 28.1s | correct diagnosis, high confidence |
| P3 PromptedOutput | universal fallback; inline `<think>` blocks | **PASS** | 20.5s | think-blocks handled, JSON parsed |
| P4 Tool loop | agent calls exploration tool, uses result | **FAIL** | 11.0s | retry exhaustion |
| P5 ModelRetry (tool mode) | validator bounce + self-correction | **FAIL** | 53.9s | retry exhaustion |
| P5 ModelRetry (prompted mode) | validator bounce + self-correction | **PASS** | 16.6s | 2 attempts → corrected unique locator |
| P6 Healing task (ToolOutput) | realistic proposals + code-side verification | **FAIL** | 642s | retry exhaustion after long reasoning |

Raw curl confirmed MiniMax **tool calling works at the API level** (clean `tool_calls`, valid JSON args, `finish_reason: tool_calls`) — the breakage is in the pydantic-ai default profile interaction. MiniMax-M2.5 emits inline `<think>…</think>` blocks; pydantic-ai's prompted path handles them.

## Probe 2 — root cause isolation, MiniMax-M2.5 (`probe2.py`)

Variants over `OpenAIModelProfile(openai_supports_strict_tool_definition=strict, openai_supports_tool_choice_required=tcr)` on the P1 triage task, then retests:

| Variant | Result | Time | Note |
|---|---|---|---|
| baseline strict=T, tcr=T | PASS | **311.3s** | flaky: same config FAILED in probe 1 at 14.5s |
| H1 strict=F, tcr=T | FAIL | 34.5s | strict-stripping alone does NOT fix it |
| H2 strict=T, **tcr=F** | **PASS** | **13.8s** | 22× faster than baseline |
| H1+H2 strict=F, tcr=F | PASS | 16.9s | |
| P4 retest (tool loop), tcr=F | FAIL | 21.5s | exploration loop still unreliable |
| P6 retest (healing), tcr=F | **PASS** | **12.6s** | was 642s-FAIL on defaults |

**Root cause: forced `tool_choice` (required/named function).** MiniMax mishandles it — responses intermittently omit the demanded tool call or burn minutes of reasoning. With `openai_supports_tool_choice_required=False`, tool-transport output becomes fast and reliable. Strict tool definitions are tolerated (and stripping them alone made things worse, likely noise/flakiness). Multi-step exploration tool loops remain unreliable on M2.5 regardless of profile.

## Probe 3 — OpenRouter small-model matrix, pydantic-ai defaults (`probe3.py`)

A=ToolOutput, B=PromptedOutput, C=exploration tool loop, D=ModelRetry/prompted:

| Model | A | B | C | D | Notes |
|---|---|---|---|---|---|
| openai/gpt-4.1-nano | PASS 2.0s | PASS 2.1s | FAIL | PASS 2.0s | C: called tool once, wrong final class |
| google/gemini-2.5-flash-lite | PASS 0.7s | **FAIL** 1.7s | FAIL | PASS 1.2s | prompted-mode *quality* miss (classified `timing`) |
| qwen/qwen3-14b | ERR 404 | PASS 49.5s | ERR 404 | PASS 85.9s | OpenRouter: "no endpoints support tools" for this model; prompted-only, slow reasoning |
| mistralai/ministral-8b | ERR | ERR | ERR | ERR | model id has no endpoints on OpenRouter (404) |
| meta-llama/llama-3.1-8b-instruct | FAIL | ERR | FAIL (0 tool calls) | PASS 3.5s (3 attempts) | prompted triage with enum failed; retry loop still converged |

## Consequences for the design (confirmed / revised)

1. **CONFIRMED (load-bearing): `ModelRetry` verification via output validator is the most portable mechanism** — passed on MiniMax (prompted) and 4/4 reachable OpenRouter models, including llama-3.1-8b needing 3 attempts. Live-session verification must live in output validators, never depend on tool calling (design D5).
2. **CONFIRMED: capability profiles must be per-model and probed, not assumed.** Failures differ in kind per model: transport (MiniMax default, qwen no-tool-endpoints), quality (flash-lite prompted misclassification, llama prompted schema), availability (ministral 404). A global output mode is wrong; `heal doctor` + per-role resolution is necessary (D5).
3. **NEW: the MiniMax profile fix is `openai_supports_tool_choice_required=False`** (not strict-stripping). The ModelFactory must ship per-backend profile presets; strict-stripping remains relevant for vLLM (documented upstream) but is not the MiniMax issue.
4. **CONFIRMED: exploration tool loops are the least reliable path on every small model tested** — gate exploration tools to `tools: reliable` models (probed, not assumed); default to engine-curated evidence excerpts. Triage/locator agents must work tool-free.
5. **CONFIRMED: budgets are mandatory.** Latency variance spans 0.7s (flash-lite) to 311s (MiniMax tool baseline) for the *same task*. Per-failure wall-clock caps and per-run ledgers (D5); fast cheap models (nano/flash-lite class) are the right default tier for triage.
6. **Practical defaults**: triage → small fast model, tool or native transport when probed-OK; locator → prompted+validator floor everywhere; doctor must catch 404/no-tool-endpoint misconfigurations with actionable messages (validated: error bodies are clear and parseable).

## Probe 4 — end-to-end latency in real RF runs (task 4.6, 2026-06-10)

Locator-drift atest (`tests/atest/heal/heal_locator_drift.robot`, real Chromium, via the `SelfHealing` shim):

| Backend | First heal (incl. 3s keyword timeout) | Greedy reuse | Note |
|---|---|---|---|
| MiniMax-M2.5 (prompted) | 18.6s | 0.2s, zero LLM calls | suite total 22s |
| gpt-4.1-nano via OpenRouter (prompted floor) | 6.9s | 0.2s | suite total 10s |
| MiniMax-M2.5 (native + validator) | FAILED / >60s budget | — | see below |

Timing-class atest (no LLM): healed by waiting 2.0s, deterministic.

**New finding: NativeOutput is NOT reliable under ModelRetry validator loops on
MiniMax-M2.5** — single-shot native passed (P2) but the locator agent with a
live-verification validator failed/spent 54–97s per transaction in native mode
and became fast and reliable (≈15s) in prompted mode. The MiniMax preset now
resolves `structured_output=prompted`; the reliability statement "prompted is
the universal floor" extends to "prompted is the only probe-proven mode under
validator retry loops" on this backend.

**Budget default**: `HEAL_MAX_FAILURE_SECONDS=60` is comfortable for prompted-mode
healing on both reference backends (15s worst observed); reasoning-model native/tool
modes are the pathological cases and are no longer defaults.
