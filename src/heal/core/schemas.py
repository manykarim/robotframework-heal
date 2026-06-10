"""Typed models flowing through the healing engine, reports, MCP and CLI.

Two tiers, per the schema-austerity rule:

* **Agent-facing** models (`Diagnosis`, `LocatorProposals`) are flat — string
  enums, no unions, at most one nesting level — so small models can emit them
  via prompted JSON.
* **Engine-assembled** models (`FailureContext`, `HealOutcome`, `FixProposal`,
  `RcaRecord`, `HealEvent`) may be rich; they are built by code from small
  typed pieces and are the contract shared by the run store, the report
  renderers, the MCP server and the CLI.

Everything is JSON-serializable; a serialized `FailureContext` is a replayable
fixture for offline triage tests and evals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- enums


class FailureClass(str, Enum):
    LOCATOR_DRIFT = "locator-drift"
    TIMING = "timing"
    VIEWPORT = "viewport"
    OVERLAY = "overlay"
    FORM_STATE = "form-state"
    ASSERTION_DRIFT = "assertion-drift"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OutcomeStatus(str, Enum):
    HEALED = "healed"
    UNHEALED = "unhealed"
    SUPPRESSED = "suppressed"


class ActionType(str, Enum):
    WAIT = "wait"
    SCROLL = "scroll"
    SWIPE = "swipe"
    DISMISS = "dismiss"
    RELOCATE = "relocate"
    RERUN = "rerun"
    FILL = "fill"


class BlastRadius(str, Enum):
    LOCAL = "local"
    SHARED = "shared"


class EvidenceKind(str, Enum):
    RF_METADATA = "rf-metadata"
    DOM_EXCERPT = "dom-excerpt"
    SCREENSHOT = "screenshot"
    CONSOLE_LOG = "console-log"
    NETWORK_LOG = "network-log"
    GIT_HISTORY = "git-history"
    SOURCE_EXCERPT = "source-excerpt"


# ----------------------------------------------------------------- agent-facing


class Diagnosis(BaseModel):
    """Triage agent output. Flat on purpose — emittable by 8B models."""

    failure_class: FailureClass
    confidence: Confidence
    rationale: str = ""


class LocatorProposals(BaseModel):
    """Locator agent output: candidate locators, best first."""

    locators: list[str]
    rationale: str = ""


# ------------------------------------------------------------- engine-assembled


class Evidence(BaseModel):
    """One collected piece of evidence; excerpts are bounded, never whole files."""

    kind: EvidenceKind
    summary: str = ""
    excerpt: str = ""
    path: str | None = None  # e.g. screenshot file relative to the report dir


class KeywordCall(BaseModel):
    """The failing keyword as the listener saw it."""

    name: str
    args: list[str] = Field(default_factory=list)
    owner_library: str = ""
    assign: list[str] = Field(default_factory=list)
    lineno: int | None = None
    source: str | None = None  # absolute path of the .robot/.resource file


class FailureContext(BaseModel):
    """Immutable, serializable context for one failed keyword."""

    keyword: KeywordCall
    error_message: str
    test_name: str = ""
    suite_name: str = ""
    failed_locator: str | None = None
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def evidence_of(self, kind: EvidenceKind) -> Evidence | None:
        return self.evidence.get(kind.value)


class HealAction(BaseModel):
    """One concrete remedy the engine applied (or tried to)."""

    type: ActionType
    description: str = ""
    params: dict[str, str] = Field(default_factory=dict)


class Attempt(BaseModel):
    action: HealAction
    succeeded: bool
    detail: str = ""


class ModelUsage(BaseModel):
    """What it cost to process one transaction."""

    model: str = ""
    output_mode: str = ""
    requests: int = 0
    total_tokens: int = 0


class HealOutcome(BaseModel):
    status: OutcomeStatus
    diagnosis: Diagnosis
    attempts: list[Attempt] = Field(default_factory=list)
    healed_locator: str | None = None
    return_value_repr: str | None = None
    duration_seconds: float = 0.0
    usage: ModelUsage = Field(default_factory=ModelUsage)
    detail: str = ""
    #: when UNHEALED, a plugin may hand over to one other failure class
    #: (single hop, e.g. Appium swipe-search not found -> locator-drift)
    fallthrough_to: FailureClass | None = None


class FixUsageSite(BaseModel):
    file: str
    lineno: int
    context: str = ""


class FixProposal(BaseModel):
    """A proposed permanent change to test source, with safety metadata."""

    file: str
    lineno: int | None = None
    kind: str = "locator"  # locator | variable | argument | assertion
    target: str = ""  # e.g. variable name or keyword name
    old_value: str = ""
    new_value: str = ""
    blast_radius: BlastRadius = BlastRadius.LOCAL
    usages: list[FixUsageSite] = Field(default_factory=list)
    rationale: str = ""
    confidence: Confidence = Confidence.MEDIUM


class RcaRecord(BaseModel):
    """Root-cause analysis — produced for EVERY transaction."""

    failure_class: FailureClass
    clean_message: str
    root_cause: str = ""
    suggested_fix: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM


class HealEvent(BaseModel):
    """One line in the JSONL run store; the unit all reporting consumes."""

    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    test_name: str = ""
    suite_name: str = ""
    source: str | None = None
    lineno: int | None = None
    keyword: KeywordCall | None = None
    context: FailureContext | None = None
    outcome: HealOutcome | None = None
    rca: RcaRecord | None = None
    fix_proposal: FixProposal | None = None

    def to_jsonl(self) -> str:
        return self.model_dump_json(exclude_none=True)

    @classmethod
    def from_jsonl(cls, line: str) -> HealEvent:
        return cls.model_validate_json(line)
