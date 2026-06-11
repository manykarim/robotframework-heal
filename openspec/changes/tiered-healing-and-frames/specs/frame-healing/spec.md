# frame-healing

## ADDED Requirements

### Requirement: Interaction-target blocklist
The locator pipeline SHALL never propose, verify, or apply `iframe`, `frame`, `html`, `body`, or `head` elements as targets for interaction keywords; such candidates SHALL be rejected with feedback naming the rule.

#### Scenario: Iframe is not a click target
- **WHEN** the locator agent proposes a locator resolving to an `<iframe>` for a Click keyword
- **THEN** the proposal is rejected during verification and the model receives feedback that frames are containers, not targets

### Requirement: Frame content in DOM evidence
WHEN the page contains same-origin `iframe`/`frame` elements, the Browser driver's page source SHALL include each frame's serialized DOM in a clearly delimited section stating the frame's pierce prefix; per-frame content SHALL be bounded and frames filtered (visible, same-origin, above minimum size).

#### Scenario: Frame DOM visible to the engine
- **WHEN** a keyword fails and the page embeds a same-origin iframe
- **THEN** the DOM evidence contains the iframe's content tagged with its `<frame-selector> >>> ` prefix

#### Scenario: Cross-origin frame degrades gracefully
- **WHEN** a frame's content cannot be serialized (cross-origin)
- **THEN** evidence notes the inaccessible frame and healing proceeds on the remaining DOM

### Requirement: Frame-pierced healing
The locator agent MAY propose `frame-selector >>> inner-selector` locators; these SHALL be verified with the same live checks (count, visibility, type compatibility) and applied via rerun unchanged.

#### Scenario: Element inside an iframe is healed
- **WHEN** a broken locator's intended target lives inside a same-origin iframe
- **THEN** the heal produces a verified `frame >>> inner` locator and the rerun succeeds, with no interaction on the frame element itself
