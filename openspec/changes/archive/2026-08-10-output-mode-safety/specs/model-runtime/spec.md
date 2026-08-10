# model-runtime (delta)

## ADDED Requirements

### Requirement: Output-mode safety rule
Before healing with a resolved structured-output mode, the runtime SHALL verify that the configured model can produce it, and SHALL fall back to a probed-working mode when it cannot. A mode that passes its probe SHALL NOT be overridden, because a probe establishes whether a transport works and not whether it heals better: `gemma-3-4b` passes both the native and prompted probes yet heals 75% prompted against 35% native, and MiniMax probes tool-capable yet is deliberately pinned to prompted on separate evidence. The verification SHALL cost at most one probe call per endpoint in the common case, SHALL be cached per endpoint for the run so roles sharing a model are probed once, SHALL run outside the per-failure time budget, and SHALL be disableable by configuration. A correction SHALL be surfaced to the user rather than applied silently.

#### Scenario: Broken configured mode falls back to one that works
- **WHEN** the resolved output mode fails its probe and another mode passes
- **THEN** healing uses the passing mode, and the correction is reported

#### Scenario: Working mode is never second-guessed
- **WHEN** the resolved output mode passes its probe
- **THEN** healing uses it, even if another mode also passes

#### Scenario: Probing is skipped when disabled
- **WHEN** capability probing is disabled by configuration
- **THEN** no probe call is made and the resolved mode is used unchanged

#### Scenario: Unprobeable endpoint keeps the configured mode
- **WHEN** no mode can be probed successfully
- **THEN** the configured mode is used unchanged rather than healing being blocked
