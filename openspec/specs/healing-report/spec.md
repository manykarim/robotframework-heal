# healing-report Specification

## Purpose
TBD - created by archiving change agentic-heal-rewrite. Update Purpose after archive.
## Requirements
### Requirement: Append-only run store
Every healing transaction SHALL append one typed event (diagnosis, evidence references, actions, outcome, fix proposal reference, model/output-mode used, token usage) to a JSONL store under the RF output directory as it completes — not at end-of-run — so a crashed run loses no recorded events.

#### Scenario: Crash-safe events
- **WHEN** the RF process is killed mid-run after two healed failures
- **THEN** both events are present and parseable in the store

#### Scenario: Rerun merge
- **WHEN** a `--rerunfailed` run completes after an initial run
- **THEN** report generation merges both stores, deduplicating events for the same source location and keeping the latest outcome

### Requirement: HTML dashboard
Report generation SHALL render a self-contained HTML dashboard from the store: run summary (healed / unhealed / suppressed counts, total cost), failure-class breakdown, and per-event drill-down (clean message, evidence including before/after screenshots when collected, diff of proposed fix, confidence, model tier).

#### Scenario: Unhealed failures are first-class
- **WHEN** a run contains failures that could not be healed
- **THEN** the dashboard lists them with their RCA records, not only the healed ones

### Requirement: Machine-readable summary
Report generation SHALL emit a `summary.json` (counts per failure class and outcome, affected files, cost totals, fix-proposal tiers) suitable for CI gates, and a GitHub annotation output mode for PR feedback.

#### Scenario: CI gate on heal count
- **WHEN** a pipeline reads `summary.json`
- **THEN** it can fail the build if healed-failure count exceeds a threshold

### Requirement: Cross-run history
Healing events SHALL be recorded in a persistent local history (SQLite) keyed by locator/source location, queryable for repeat-healing signals.

#### Scenario: Flaky locator surfaced
- **WHEN** the same locator is healed in 4 runs within 30 days
- **THEN** the dashboard flags it as a maintenance hotspot with its healing history

