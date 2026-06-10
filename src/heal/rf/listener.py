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


#: owning library -> driver factory(library_instance)
DRIVER_FACTORIES = {
    "Browser": _make_browser_driver,
    "AppiumLibrary": _make_appium_driver,
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
        self.fixed_locators: dict[str, str] = {}
        self._in_transaction = False
        self._artifact_dir: str | None = None

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

        self._enrich_fix_proposal(event)
        self.events.append(event)
        self._store_event(event)
        self._apply_outcome(event, session, result)

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

        Honors the same suppression rule as end_keyword: keywords inside
        expected-failure wrappers must fail authentically, so no proactive
        substitution there either.
        """
        if not self.fixed_locators or result.owner not in DRIVER_FACTORIES:
            return
        if getattr(getattr(data, "parent", None), "name", None) in SKIP_PARENT_KEYWORDS:
            return
        if not getattr(data, "args", None):
            return
        try:
            first_arg = str(BuiltIn().replace_variables(str(data.args[0])))
        except Exception:
            return
        healed = self.fixed_locators.get(first_arg)
        if not healed:
            return
        driver = self._driver_for(result.owner)
        if driver is None:
            return
        if driver.count(first_arg) == 0 and driver.count(healed) > 0:
            data.args = list(data.args)
            data.args[0] = healed
            result.args = data.args
            logger.info(f"heal: proactively replaced known-broken locator with {healed!r}", also_console=True)

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
            if resolved.kind != "literal":
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
        dashboard = render_dashboard(events, Path(directory) / "heal_report.html", hotspots)
        write_summary(events, Path(directory) / "summary.json")
        self._write_fixes(events, Path(directory))
        logger.info(f"heal: report written to {dashboard}", also_console=True)

    def _write_fixes(self, events, directory) -> None:
        """End-of-run fix synthesis: healed copies + patch; in-place opt-in."""
        from ..core.settings import FixTier
        from ..fix.apply import apply_in_place, synthesize_changes, unified_patch, write_healed_copies
        from ..fix.resolve import resolve_fix

        if self.settings.fix_tier is FixTier.REPORT:
            return
        proposals = [e.fix_proposal for e in events if e.fix_proposal and e.fix_proposal.kind == "locator"]
        if not proposals:
            return
        fixes = [
            resolve_fix(
                file=p.file, lineno=p.lineno,
                old_locator=p.old_value, new_locator=p.new_value,
            )
            for p in proposals
        ]
        auto = [f for f in fixes if f.blast_radius == "local"]
        shared = [f for f in fixes if f.blast_radius == "shared"]
        result = synthesize_changes(auto + shared)
        write_healed_copies(result, directory / "healed_files")
        patch = unified_patch(result, repo_root=_repo_root(proposals[0].file))
        if patch:
            (directory / "heal.patch").write_text(patch, encoding="utf-8")
            logger.info(f"heal: fix patch written to {directory / 'heal.patch'}", also_console=True)
        if self.settings.fix_tier is FixTier.IN_PLACE:
            safe = synthesize_changes(auto)  # shared blast radius never auto-applies
            written, refused = apply_in_place(safe)
            for path in written:
                logger.info(f"heal: applied fix in place: {path}", also_console=True)
            for path in refused:
                logger.warn(f"heal: in-place fix refused (dirty git tree): {path}")
