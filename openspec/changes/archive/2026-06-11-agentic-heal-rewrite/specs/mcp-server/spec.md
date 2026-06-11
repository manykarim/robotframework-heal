# mcp-server

## ADDED Requirements

### Requirement: MCP server over the heal core
The package SHALL provide an MCP server (stdio transport minimum) exposing: the run store as resources (failure bundles with evidence, fix proposals), and tools to query healing history, render reports, and apply fix proposals.

#### Scenario: Coding agent reads a failure bundle
- **WHEN** an MCP client requests a failure bundle resource
- **THEN** it receives the typed event: diagnosis, clean message, evidence excerpts, attempted actions, and fix proposal with blast radius

#### Scenario: Fix application respects tiers
- **WHEN** an MCP client calls `apply_fix` for a `shared` blast-radius proposal
- **THEN** the server refuses in-place application and returns the patch plus usage list for the agent to act on

### Requirement: Live session toolset (attached mode)
WHEN started in attached mode against a live automation session, the MCP server SHALL expose the same driver toolset used by in-process agents (query DOM, element info, screenshot, scroll/swipe, dismiss overlay) so a coding agent can investigate interactively.

#### Scenario: Same tool surface as embedded agents
- **WHEN** the driver toolset gains a new tool
- **THEN** the MCP server exposes it without separate MCP-specific code

### Requirement: Agent skill documentation
The repository SHALL ship an agent skill (instructions document) describing the triage→inspect→fix workflow over the MCP/CLI surface for coding agents.

#### Scenario: Skill references real commands
- **WHEN** the skill instructs starting the server or applying fixes
- **THEN** the referenced commands exist (`heal mcp`, `heal apply`) and match current CLI behavior
