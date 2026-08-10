"""The Robot Framework listener: thin shell over the healing engine.

Responsibilities (and nothing more):
* qualify failures (owning library has a driver, parent not in skip list,
  no transaction active, healing enabled)
* assemble the ContextBuilder and RF session
* run the transaction with the per-failure budget
* apply the outcome: result status, return-value assignment, log messages
* greedy reuse of known broken->healed locator mappings
"""

from __future__ import annotations

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn

from ..core.engine import HealingEngine
from ..core.evidence import ContextBuilder
from ..core.ledger import RunLedger
from ..core.runtime import AgentRuntime
from ..core.schemas import HealEvent, KeywordCall, OutcomeStatus
from ..core.settings import HealSettings
from .executor import TransactionRuntime
from .session import RfHealSession

SKIP_PARENT_KEYWORDS = (
    "Run Keyword And Return Status",
    "Run Keyword And Expect Error",
    "Run Keyword And Ignore Error",
    "Run Keyword And Continue On Failure",
)


def _repo_root(file_path: str) -> str | None:
    import subprocess
    from pathlib import Path

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(Path(file_path).parent), capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def _make_browser_driver(instance):
    from ..drivers.browser import BrowserDriver

    return BrowserDriver(instance)


def _make_appium_driver(instance):
    from ..drivers.appium import AppiumDriver

    return AppiumDriver(instance)


def _make_selenium_driver(instance):
    from ..drivers.selenium import SeleniumDriver

    return SeleniumDriver(instance)


#: owning library -> driver factory(library_instance)
DRIVER_FACTORIES = {
    "Browser": _make_browser_driver,
    "AppiumLibrary": _make_appium_driver,
    "SeleniumLibrary": _make_selenium_driver,
}


class HealListener:
    """Use as `Library    heal.rf.HealListener` or `--listener heal.rf.HealListener`."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, settings: HealSettings | None = None):
        self.ROBOT_LIBRARY_LISTENER = self
        self.settings = settings or HealSettings()
        self.agent_runtime = AgentRuntime(self.settings)
        self.ledger = RunLedger(settings=self.settings)
        self.engine = HealingEngine(self.agent_runtime, self.ledger)
        self.txn_runtime = TransactionRuntime()
        self.events: list[HealEvent] = []
        self._reported_notes: list[str] = []
        self.fixed_locators: dict[str, str] = {}
        #: (source file, broken locator) -> healed locator, loaded from history
        self.warm_fixes: dict[tuple[str, str], str] = {}
        self._warm_loaded = False
        self._in_transaction = False
        self._artifact_dir: str | None = None
        self._event_counter = 0

    # ------------------------------------------------------------ RF lifecycle

    def start_keyword(self, data, result):
        if not self.settings.enabled or self._in_transaction:
            return
        self._apply_known_fix(data, result)

    def end_keyword(self, data, result):
        if not self._qualifies(data, result):
            return
        driver = self._driver_for(result.owner)
        if driver is None:
            return

        self._in_transaction = True
        try:
            event, session = self._run_transaction(data, result, driver)
        except TimeoutError as exc:
            logger.warn(f"heal: transaction abandoned: {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - never fail the run harder
            logger.warn(f"heal: engine error: {type(exc).__name__}: {exc}")
            return
        finally:
            self._in_transaction = False

        self._report_capability_notes()
        self._enrich_fix_proposal(event)
        self.events.append(event)
        self._store_event(event)
        self._apply_outcome(event, session, result)

    def _report_capability_notes(self) -> None:
        """Surface an output-mode correction once — silently healing in a mode
        the user did not configure would be worse than the failure it avoids."""
        runtime = getattr(self.engine, "runtime", None)
        notes = list(getattr(runtime, "capability_notes", ()) or ())
        for note in notes[len(self._reported_notes) :]:
            logger.warn(f"heal: {note}")
            self._reported_notes.append(note)

    def close(self):
        try:
            self._write_reports()
        except Exception as exc:  # noqa: BLE001 - reporting must not fail the run
            logger.warn(f"heal: report generation failed: {type(exc).__name__}: {exc}")
        finally:
            self.txn_runtime.shutdown()

    # ------------------------------------------------------------------ stages

    def _qualifies(self, data, result) -> bool:
        if not self.settings.enabled or self._in_transaction:
            return False
        if not result.failed:
            return False
        if result.owner not in DRIVER_FACTORIES:
            return False
        parent_name = getattr(getattr(data, "parent", None), "name", None)
        if parent_name in SKIP_PARENT_KEYWORDS:
            return False
        return True

    def _driver_for(self, owner: str):
        factory = DRIVER_FACTORIES.get(owner)
        if factory is None:
            return None
        try:
            instance = BuiltIn().get_library_instance(owner)
        except Exception:
            return None
        return factory(instance)

    def _run_transaction(self, data, result, driver) -> tuple[HealEvent, RfHealSession]:
        session = RfHealSession(driver, self.txn_runtime)
        builder = ContextBuilder(
            keyword=self._keyword_call(data, result),
            error_message=result.message or "",
            test_name=self._variable("${TEST NAME}"),
            suite_name=self._variable("${SUITE NAME}"),
            failed_locator=self._failed_locator(data),
            driver=session.driver,
            artifact_dir=self._artifacts(),
        )
        event = self.txn_runtime.run_transaction(
            self.engine.handle(builder, session),
            timeout_seconds=self.settings.max_failure_seconds,
        )
        return event, session

    def _apply_outcome(self, event: HealEvent, session: RfHealSession, result):
        outcome = event.outcome
        if outcome is None:
            return
        if event.rca is not None:
            logger.info(f"heal: {event.rca.clean_message}", also_console=True)
        if outcome.status is not OutcomeStatus.HEALED:
            if outcome.detail:
                logger.info(f"heal: {outcome.detail}")
            for attempt in outcome.attempts:
                logger.info(f"heal attempt: {attempt.action.description} -> {attempt.detail or 'ok'}")
            return
        if outcome.healed_locator and event.context and event.context.failed_locator:
            self.fixed_locators[event.context.failed_locator] = outcome.healed_locator
        if result.assign and session.last_return_value is not None:
            BuiltIn().set_local_variable(result.assign[0], session.last_return_value)
        result.status = "PASS"

    def _apply_known_fix(self, data, result):
        """Greedy reuse: swap a known-broken locator before the keyword runs.

        Sources: this run's heals, then warm-started mappings from the healing
        history (scoped to the keyword's source file). Honors the same
        suppression rule as end_keyword: keywords inside expected-failure
        wrappers must fail authentically, so no proactive substitution there.
        """
        self._load_warm_fixes()
        if not (self.fixed_locators or self.warm_fixes) or result.owner not in DRIVER_FACTORIES:
            return
        if getattr(getattr(data, "parent", None), "name", None) in SKIP_PARENT_KEYWORDS:
            return
        if not getattr(data, "args", None):
            return
        try:
            first_arg = str(BuiltIn().replace_variables(str(data.args[0])))
        except Exception:
            return
        source = str(data.source) if getattr(data, "source", None) else ""
        healed = self.fixed_locators.get(first_arg)
        from_history = False
        if not healed:
            healed = self.warm_fixes.get((source, first_arg))
            from_history = healed is not None
        if not healed:
            return
        driver = self._driver_for(result.owner)
        if driver is None:
            return
        if driver.count(first_arg) == 0 and driver.count(healed) > 0:
            data.args = list(data.args)
            data.args[0] = healed
            result.args = data.args
            origin = "history" if from_history else "this run"
            logger.info(
                f"heal: proactively replaced known-broken locator with {healed!r} (from {origin})",
                also_console=True,
            )
            if from_history:
                self._record_warm_event(data, result, first_arg, healed)

    def _load_warm_fixes(self):
        """Lazy warm start from the healing history (task: heal-memory)."""
        if self._warm_loaded or not self.settings.warm_start:
            self._warm_loaded = True
            return
        self._warm_loaded = True
        directory = self._artifacts()
        from pathlib import Path

        history_path = self.settings.history_db or (f"{directory}/history.sqlite" if directory else None)
        if not history_path or not Path(history_path).is_file():
            return
        try:
            from ..report.history import HealHistory

            for source, failed, healed in HealHistory(history_path).recent_mappings():
                self.warm_fixes.setdefault((source, failed), healed)
            if self.warm_fixes:
                logger.info(f"heal: warm-started {len(self.warm_fixes)} known fix(es) from history")
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"heal: warm start failed: {exc}")

    def _record_warm_event(self, data, result, broken: str, healed: str):
        """Provenance: history-reused swaps appear in reports as heal events."""
        from ..core.schemas import (
            ActionType,
            Attempt,
            Confidence,
            Diagnosis,
            FailureClass,
            FailureContext,
            HealAction,
            HealOutcome,
            OutcomeStatus,
        )

        self._event_counter += 1
        keyword_call = self._keyword_call(data, result)
        event = HealEvent(
            event_id=f"warm-{self._event_counter}",
            test_name=self._variable("${TEST NAME}"),
            suite_name=self._variable("${SUITE NAME}"),
            source=str(data.source) if getattr(data, "source", None) else None,
            lineno=getattr(data, "lineno", None),
            keyword=keyword_call,
            # context carries the broken locator so history.record keeps the
            # mapping alive (recent_mappings requires failed_locator)
            context=FailureContext(
                keyword=keyword_call,
                error_message="(not executed: known-broken locator replaced proactively)",
                test_name=self._variable("${TEST NAME}"),
                suite_name=self._variable("${SUITE NAME}"),
                failed_locator=broken,
            ),
            outcome=HealOutcome(
                status=OutcomeStatus.HEALED,
                diagnosis=Diagnosis(
                    failure_class=FailureClass.LOCATOR_DRIFT,
                    confidence=Confidence.HIGH,
                    rationale=f"Known fix reused from healing history: {broken!r} -> {healed!r}.",
                ),
                attempts=[
                    Attempt(
                        action=HealAction(
                            type=ActionType.RELOCATE,
                            description=f"warm-start reuse from history: {healed!r}",
                            params={"origin": "history", "broken": broken, "healed": healed},
                        ),
                        succeeded=True,
                    )
                ],
                healed_locator=healed,
                detail="Healed proactively from history before keyword execution (zero LLM calls).",
            ),
        )
        self.events.append(event)
        self._store_event(event)

    # ----------------------------------------------------------------- helpers

    def _keyword_call(self, data, result) -> KeywordCall:
        try:
            args = [str(BuiltIn().replace_variables(str(a))) for a in (data.args or [])]
        except Exception:
            args = [str(a) for a in (data.args or [])]
        return KeywordCall(
            name=result.name,
            args=args,
            owner_library=result.owner or "",
            assign=list(result.assign or []),
            lineno=getattr(data, "lineno", None),
            source=str(data.source) if getattr(data, "source", None) else None,
        )

    def _failed_locator(self, data) -> str | None:
        if not getattr(data, "args", None):
            return None
        try:
            return str(BuiltIn().replace_variables(str(data.args[0])))
        except Exception:
            return str(data.args[0])

    def _variable(self, name: str) -> str:
        try:
            return str(BuiltIn().get_variable_value(name) or "")
        except Exception:
            return ""

    def _artifacts(self) -> str | None:
        if self._artifact_dir is None:
            if self.settings.report_dir:
                self._artifact_dir = self.settings.report_dir
            else:
                out = self._variable("${OUTPUT DIR}")
                self._artifact_dir = f"{out}/heal" if out else None
        return self._artifact_dir

    def _enrich_fix_proposal(self, event) -> None:
        """Resolve real blast radius/usages for the event's fix proposal."""
        proposal = event.fix_proposal
        if proposal is None or proposal.kind != "locator" or not proposal.file:
            return
        try:
            from ..core.schemas import BlastRadius, FixUsageSite
            from ..fix.resolve import resolve_fix

            resolved = resolve_fix(
                file=proposal.file, lineno=proposal.lineno,
                old_locator=proposal.old_value, new_locator=proposal.new_value,
            )
            if resolved.kind == "unresolved":
                return
            proposal.blast_radius = (
                BlastRadius.SHARED if resolved.blast_radius == "shared" else BlastRadius.LOCAL
            )
            proposal.usages = [FixUsageSite(file=f, lineno=line) for f, line in resolved.usages]
            if resolved.kind == "keyword-argument":
                proposal.kind = "argument"
                proposal.target = resolved.variable_name
            elif resolved.kind != "literal":
                proposal.kind = "variable"
                proposal.target = resolved.variable_name
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"heal: blast-radius resolution failed: {exc}")

    def _store_event(self, event) -> None:
        directory = self._artifacts()
        if directory is None:
            return
        try:
            from ..report.store import RunStore

            RunStore(directory).append(event)
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"heal: could not persist event: {type(exc).__name__}: {exc}")

    def _write_reports(self) -> None:
        directory = self._artifacts()
        if directory is None or not self.events:
            return
        from pathlib import Path

        from ..report.history import HealHistory
        from ..report.html import render_dashboard
        from ..report.store import RunStore, merge_events
        from ..report.summary import write_summary

        events = merge_events(RunStore(directory).load() or self.events)
        history_path = self.settings.history_db or str(Path(directory) / "history.sqlite")
        hotspots = []
        try:
            history = HealHistory(history_path)
            history.record(self.events)
            hotspots = history.hotspots()
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"heal: history update failed: {type(exc).__name__}: {exc}")
        artifacts = None
        try:
            artifacts = self._write_fixes(events, Path(directory))
        except Exception as exc:  # noqa: BLE001
            logger.warn(f"heal: fix synthesis failed: {type(exc).__name__}: {exc}")
        dashboard = render_dashboard(
            events,
            Path(directory) / "heal_report.html",
            hotspots,
            fix_views=artifacts.proposal_views if artifacts else None,
        )
        write_summary(events, Path(directory) / "summary.json")
        logger.info(f"heal: report written to {dashboard}", also_console=True)

    def _write_fixes(self, events, directory):
        """End-of-run fix synthesis.

        Healed copies + visual diffs are ALWAYS produced (read-only artifacts;
        originals untouched). `HEAL_FIX_TIER` gates only working-tree-facing
        outputs: the unified .patch (tier patch+) and in-place edits.
        Returns the FixArtifacts for dashboard integration.
        """
        from ..core.settings import FixTier
        from ..fix.apply import apply_in_place, synthesize_changes, unified_patch
        from ..fix.service import build_fix_artifacts

        artifacts = build_fix_artifacts(events, directory)
        if not artifacts.proposals:
            return artifacts
        if artifacts.pages:
            logger.info(
                f"heal: {len(artifacts.pages)} file diff(s) written to {directory / 'diffs' / 'index.html'}",
                also_console=True,
            )

        if self.settings.fix_tier is FixTier.REPORT:
            return artifacts
        patch = unified_patch(artifacts.result, repo_root=_repo_root(artifacts.proposals[0].file))
        if patch:
            (directory / "heal.patch").write_text(patch, encoding="utf-8")
            logger.info(f"heal: fix patch written to {directory / 'heal.patch'}", also_console=True)
        if self.settings.fix_tier is FixTier.IN_PLACE:
            safe = synthesize_changes(artifacts.local_fixes)  # shared never auto-applies
            written, refused = apply_in_place(safe)
            for path in written:
                logger.info(f"heal: applied fix in place: {path}", also_console=True)
            for path in refused:
                logger.warn(f"heal: in-place fix refused (dirty git tree): {path}")
        return artifacts
