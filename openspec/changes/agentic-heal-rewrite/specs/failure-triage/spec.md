# failure-triage

## ADDED Requirements

### Requirement: Deterministic detection before LLM triage
The engine SHALL run registered deterministic detectors (no LLM calls) over the failure evidence first, and SHALL invoke the triage agent only when no detector matches unambiguously.

#### Scenario: Detector resolves the failure class
- **WHEN** a keyword fails and the locator matches 0 elements on the live page
- **THEN** the failure is classified `locator-drift` without any LLM call

#### Scenario: Ambiguous failure falls back to triage agent
- **WHEN** no deterministic detector produces an unambiguous verdict
- **THEN** the triage agent is invoked once with curated evidence and returns a `Diagnosis` with `failure_class`, `confidence` (low/medium/high), and `rationale`

### Requirement: Typed failure context
The engine SHALL assemble an immutable, serializable `FailureContext` per failed keyword, using lazy cost-tagged evidence collectors, and SHALL pass only curated excerpts (simplified DOM, bounded source lines, bounded log excerpts) to LLM agents — never whole files or raw DOM trees.

#### Scenario: Evidence collected lazily
- **WHEN** a failure is classified by a deterministic detector that needs only the element count
- **THEN** no screenshot or git evidence is collected for classification

#### Scenario: Failure context is replayable
- **WHEN** a `FailureContext` is serialized to disk and later deserialized
- **THEN** the triage pipeline produces the same diagnosis without a live session

### Requirement: Suppression rules
The engine SHALL NOT start a healing transaction when (a) the failing keyword's parent is in the skip list (`Run Keyword And Return Status`, `Run Keyword And Expect Error`, `Run Keyword And Ignore Error`, `Run Keyword And Continue On Failure`), (b) a healing transaction is already active (re-entrancy guard), or (c) a configured run/failure budget is exhausted.

#### Scenario: Expected-failure keyword is skipped
- **WHEN** a keyword fails inside `Run Keyword And Expect Error`
- **THEN** no healing transaction starts and no LLM call is made

#### Scenario: Events from healing reruns are ignored
- **WHEN** the engine reruns a keyword as part of healing and that rerun fails
- **THEN** the listener does not start a nested healing transaction

#### Scenario: Budget exhaustion degrades to RCA-only
- **WHEN** the run token budget is exhausted
- **THEN** subsequent failures are classified by deterministic detectors only and produce RCA records without healing attempts

### Requirement: Extensible failure-class registry
Failure classes SHALL be registered as plugins exposing `detect`, `heal`, and `synthesize_fix`, evaluated in priority order; adding a new failure class SHALL NOT require modifying the engine.

#### Scenario: New failure class is additive
- **WHEN** a new plugin is registered for a custom failure class
- **THEN** its detector participates in classification without engine code changes
