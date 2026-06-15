# documentation-site Specification

## Purpose
TBD - created by archiving change comprehensive-docs-site. Update Purpose after archive.
## Requirements
### Requirement: Diátaxis information architecture
The documentation site SHALL organize content into Tutorials, How-to guides, Reference, and Explanation sections, with navigation declared in `mkdocs.yml`. Coverage SHALL include, at minimum: a getting-started tutorial; how-to guides for each supported model provider, for SeleniumLibrary and Appium, for CI gating, and for fixing/reviewing files; reference for configuration, the CLI, failure classes, and drivers; and explanation pages for the failure taxonomy, the tiered locator pipeline, capability-tiered models, and the threading model.

#### Scenario: Reader finds content by intent
- **WHEN** a new user opens the site
- **THEN** the navigation presents Tutorials, How-to, Reference, and Explanation sections and a getting-started tutorial reachable from the landing page

#### Scenario: Every supported provider has a setup guide
- **WHEN** a user wants to configure a self-hosted or hosted model backend
- **THEN** a how-to guide documents the `HEAL_*` settings for that provider (at least OpenAI-compatible, vLLM/Ollama, and the MiniMax/OpenRouter reference backends)

### Requirement: Diagrams and real-output gallery
The site SHALL include mermaid diagrams of the healing pipeline and the tiered locator selection, and a gallery of images of the actual report artifacts (HTML dashboard, side-by-side diff, `heal doctor` output) captured from a real run.

#### Scenario: Behavior is shown, not only described
- **WHEN** a reader views the reporting and pipeline pages
- **THEN** they see at least one rendered mermaid diagram and at least one screenshot of a real heal report artifact

### Requirement: Versioned site, single version published
The site SHALL use a versioning mechanism capable of hosting multiple documentation versions with a version selector, while publishing exactly one default rolling version at this time. Adding a pinned version later SHALL NOT require restructuring the site.

#### Scenario: Version selector present with one version
- **WHEN** the site is deployed
- **THEN** a version selector is available and the default rolling version is served

#### Scenario: A pinned version can be added later
- **WHEN** a release version is published alongside the rolling version
- **THEN** both appear in the selector without changes to the site structure

### Requirement: GitHub Pages deployment
The site SHALL build and deploy to GitHub Pages via a CI workflow on pushes to the default branch; pull requests SHALL build the site in strict mode without deploying.

#### Scenario: Main updates the published site
- **WHEN** a commit lands on the default branch
- **THEN** the workflow builds and publishes the site to GitHub Pages

#### Scenario: Broken docs fail the PR
- **WHEN** a pull request introduces a broken internal link or build error
- **THEN** the strict build fails in CI and the PR check is red

