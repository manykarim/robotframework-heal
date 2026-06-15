import json

from heal.core.schemas import (
    ActionType,
    Attempt,
    BlastRadius,
    Confidence,
    Diagnosis,
    Evidence,
    EvidenceKind,
    FailureClass,
    FailureContext,
    FixProposal,
    FixUsageSite,
    HealAction,
    HealEvent,
    HealOutcome,
    KeywordCall,
    ModelUsage,
    OutcomeStatus,
    RcaRecord,
)


def make_context() -> FailureContext:
    return FailureContext(
        keyword=KeywordCall(
            name="Click",
            args=["id=login-button"],
            owner_library="Browser",
            lineno=42,
            source="/suites/login.robot",
        ),
        error_message="TimeoutError: waiting for locator('id=login-button')",
        test_name="Valid Login",
        suite_name="Login",
        failed_locator="id=login-button",
        evidence={
            EvidenceKind.DOM_EXCERPT.value: Evidence(
                kind=EvidenceKind.DOM_EXCERPT,
                summary="login form",
                excerpt="<form id='login-form'>...</form>",
            )
        },
    )


def test_failure_context_round_trip():
    ctx = make_context()
    restored = FailureContext.model_validate_json(ctx.model_dump_json())
    assert restored == ctx
    assert restored.evidence_of(EvidenceKind.DOM_EXCERPT).summary == "login form"
    assert restored.evidence_of(EvidenceKind.SCREENSHOT) is None


def test_agent_schemas_are_flat():
    """Austerity guard: agent-facing schemas must stay shallow (enums + scalars)."""
    for field in Diagnosis.model_fields.values():
        assert field.annotation in (FailureClass, Confidence, str)


def test_heal_event_jsonl_round_trip():
    event = HealEvent(
        event_id="t1-k42",
        test_name="Valid Login",
        suite_name="Login",
        source="/suites/login.robot",
        lineno=42,
        context=make_context(),
        outcome=HealOutcome(
            status=OutcomeStatus.HEALED,
            diagnosis=Diagnosis(
                failure_class=FailureClass.LOCATOR_DRIFT,
                confidence=Confidence.HIGH,
                rationale="locator missing, similar button present",
            ),
            attempts=[
                Attempt(
                    action=HealAction(type=ActionType.RELOCATE, description="css=#signin-btn"),
                    succeeded=True,
                )
            ],
            healed_locator="css=#signin-btn",
            duration_seconds=12.5,
            usage=ModelUsage(model="MiniMax-M2.5", output_mode="prompted", requests=2, total_tokens=4321),
        ),
        rca=RcaRecord(
            failure_class=FailureClass.LOCATOR_DRIFT,
            clean_message="The login button id changed from 'login-button' to 'signin-btn'.",
            suggested_fix="Update the locator in login.robot:42",
        ),
        fix_proposal=FixProposal(
            file="/suites/login.robot",
            lineno=42,
            old_value="id=login-button",
            new_value="css=#signin-btn",
            blast_radius=BlastRadius.SHARED,
            usages=[FixUsageSite(file="/suites/login.robot", lineno=42)],
        ),
    )
    line = event.to_jsonl()
    assert "\n" not in line
    restored = HealEvent.from_jsonl(line)
    assert restored == event
    # enums serialize as their wire values
    assert json.loads(line)["outcome"]["status"] == "healed"
    assert json.loads(line)["rca"]["failure_class"] == "locator-drift"


def test_minimal_event_excludes_none():
    line = HealEvent(event_id="x").to_jsonl()
    payload = json.loads(line)
    assert "context" not in payload and "outcome" not in payload
