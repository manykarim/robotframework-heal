# Findings: RF threading spike (design D4)

**Date**: 2026-06-10 · **RF**: 7.x · **Gate for**: tasks 3.6/3.7, design decision D4

Spike: `spike_listener.py` (uses the production `heal.rf.executor.TransactionRuntime`) + `spike.robot`, run with `uv run robot --listener spike_listener spike.robot`.

## Result: 4/4 tests PASS — the model works as designed

| Claim | Evidence |
|---|---|
| Persistent healer loop + blocked-main-thread serving works inside listener v3 `end_keyword` | Both healing tests PASS |
| Keyword rerun via `BuiltIn().run_keyword` marshalled from the loop to the main thread works | rerun executed, follow-up assertions PASS |
| Return-value assignment after heal works (`${value} =` receives the heal's return value via `set_local_variable`) | test asserts the assigned value |
| Parallel async work on the loop while RF reads marshal to main (asyncio.gather of fake-LLM + `get_variable_value`) | transaction outcome contains both results |
| Loop survives across tests/transactions (built once, reused) | second test heals identically |
| Abandonment: hanging transaction times out, unblocks the listener, the run continues | hang test + follow-up test PASS; `TimeoutError` raised after timeout+grace |
| Log/output integrity | output.xml/log.html generated cleanly, healed keywords show PASS |

## Notes & consequences

1. **Re-entrancy guard is mandatory and sufficient**: a simple `in_transaction` flag on the listener stops rerun-triggered `end_keyword` events from spawning nested transactions (matches the engine design; the listener owns the flag).
2. **Abandonment grace**: `ABANDON_GRACE_SECONDS=10` on top of the per-failure budget blocks the run for up to budget+10s in the worst case. Acceptable; the abandoned coroutine is cancelled and pending main-calls are failed with `TransactionAbandoned`, so no leak and no deadlock was observed.
3. **`call_on_main` from `asyncio.to_thread` workers** (how plugins call sync driver methods) works; `MainThreadProxy` makes it transparent.
4. **No fallback needed**: the portal/run_sync fallback documented in design.md Risks does not need to be built.
