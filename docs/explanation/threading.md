# Threading and execution model

This is the load-bearing piece of plumbing. Three facts collide:

1. Robot Framework listener callbacks are **synchronous**.
2. pydantic-ai agents are **async** and should be reused across a run.
3. The Browser/Appium library instance is only safe on RF's **main thread**.

## The actor model

heal runs one persistent asyncio loop on a dedicated thread. The listener submits
a healing transaction and then *services a request queue while blocked* — any
driver or RF call the engine needs is marshalled back to the main thread, while
the LLM work runs on the healer loop.

```mermaid
sequenceDiagram
    participant Main as RF main thread
    participant Loop as healer loop
    Main->>Loop: submit transaction
    activate Loop
    Loop->>Loop: agents + evidence (parallel)
    Loop-->>Main: need DOM / screenshot / rerun?
    Main->>Main: execute on main thread
    Main-->>Loop: result
    Loop-->>Main: HealOutcome + RCA
    deactivate Loop
    Main->>Main: apply outcome (status, assign, log)
```

This single structure solves all three constraints at once: the browser is only
ever touched on the main thread; agents get a real, reused event loop with parallel
LLM calls; and there is no nested-event-loop fragility.

## Re-entrancy and abandonment

- **Re-entrancy guard**: while a transaction is active, listener events triggered
  by heal's *own* keyword reruns are ignored (a single flag the engine owns) — so
  a rerun never spawns a nested transaction.
- **Abandonment**: if a transaction exceeds its budget, the listener unblocks
  after a grace period, the keyword stays failed, and the run continues — a hung
  agent never hangs the suite.

## Proven, not assumed

A spike ran this model inside a real Robot Framework run: **4/4 tests passed** —
keyword rerun, return-value assignment, parallel loop work, and timeout
abandonment all behaved as designed, with clean `output.xml`/`log.html`. No
fallback design was needed.

*Source: `experiments/rf-threading/FINDINGS.md`.*
