# generated-reference

## ADDED Requirements

### Requirement: Configuration reference generated from the settings schema
The user-facing configuration reference SHALL be generated at build time from the `HealSettings` schema. Each setting SHALL be rendered with its environment variable name (the `HEAL_` prefix applied to the field), its type or enum choices, its default value, any value constraints, and its description. Settings SHALL be grouped by concern (e.g. feature switches, model configuration, per-role overrides, budgets, reporting).

#### Scenario: Every setting appears with its env var and default
- **WHEN** the reference is generated
- **THEN** every field of `HealSettings` appears with its `HEAL_*` env var name and default value

#### Scenario: Enum settings list their choices
- **WHEN** a setting is an enum (e.g. output mode, fix tier)
- **THEN** the reference lists the allowed values

### Requirement: CLI reference generated from the command app
The CLI reference SHALL be generated at build time from the Typer application. Every command SHALL be documented with its usage, arguments, options, and help text.

#### Scenario: Every command is documented
- **WHEN** the CLI reference is generated
- **THEN** every registered `heal` subcommand appears with its arguments and options

### Requirement: Completeness guard against drift
The reference generation SHALL fail the build when any setting lacks a description or any registered CLI command is not rendered, so documentation cannot silently drift from the code.

#### Scenario: Undocumented setting fails the build
- **WHEN** a new setting is added without a description
- **THEN** the documentation build fails until the setting is documented

#### Scenario: New command must be rendered
- **WHEN** a new CLI command is added
- **THEN** the generated reference includes it or the build fails
