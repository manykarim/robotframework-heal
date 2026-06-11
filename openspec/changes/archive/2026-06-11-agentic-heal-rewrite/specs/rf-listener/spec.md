# rf-listener

## ADDED Requirements

### Requirement: Listener v3 surface with healing transaction handoff
The package SHALL provide a Robot Framework listener (API v3, usable as library listener and `--listener`) that, on qualifying keyword failures, submits a healing transaction to the engine and applies the outcome: rerun bookkeeping, keyword result status mutation, return-value assignment, and log messages.

#### Scenario: Healed keyword reported as PASS
- **WHEN** the engine returns a successful heal outcome
- **THEN** the keyword result is PASS in log.html and the healing actions are visible as log messages

### Requirement: Main-thread driver execution
All Robot Framework and automation-library calls (keyword reruns, DOM queries, screenshots) SHALL execute on the RF main thread; the engine's event loop SHALL run on a separate persistent thread and marshal driver requests to the main thread while the listener blocks.

#### Scenario: Parallel LLM calls with serialized driver access
- **WHEN** a transaction needs a vision check and locator proposals concurrently
- **THEN** LLM calls run in parallel on the healer loop while page interactions execute serially on the main thread

#### Scenario: Engine timeout does not hang the run
- **WHEN** the engine fails to complete a transaction within the per-failure cap
- **THEN** the listener unblocks, the keyword remains FAIL, and the test run continues

### Requirement: Backward-compatible entry point
The legacy `SelfHealing` library/listener import SHALL keep working as a deprecation shim mapping legacy kwargs to new settings where semantics match, and emitting a deprecation warning naming the replacement.

#### Scenario: Existing suite unchanged
- **WHEN** a suite uses `Library    SelfHealing    fix=realtime`
- **THEN** the run works through the new engine and logs a deprecation note

### Requirement: Library-agnostic keyword qualification
The listener SHALL qualify failures by resolving the owning library to a registered driver (Browser, AppiumLibrary initially) and SHALL ignore failures from libraries without a driver.

#### Scenario: Unsupported library untouched
- **WHEN** a database keyword from an unsupported library fails
- **THEN** no healing transaction starts and the failure is unmodified
