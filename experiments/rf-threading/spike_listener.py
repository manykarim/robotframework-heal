"""Threading-spike listener: proves design D4 inside a real Robot Framework run.

For every failed keyword tagged by the suite, runs a transaction on the healer
loop that (a) does async work in parallel (simulated LLM latency), (b) reads RF
state via main-thread calls, (c) reruns the keyword with corrected args on the
main thread, and (d) mutates the result to PASS with return-value assignment.
One test exercises the abandonment path with a hanging transaction.
"""

import asyncio

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn

from heal.rf.executor import MainThreadProxy, TransactionRuntime


class spike_listener:  # noqa: N801 - RF listener naming
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self):
        self.runtime = TransactionRuntime()
        self.in_transaction = False
        self.transactions = []

    def end_keyword(self, data, result):
        if not result.failed or self.in_transaction:
            return
        if result.name == "Hang Forever Keyword":
            self._handle_hang(data, result)
            return
        if "Should Be Equal" not in result.name:
            return

        self.in_transaction = True
        try:
            outcome = self.runtime.run_transaction(self._heal(data, result), timeout_seconds=15)
        except TimeoutError as exc:
            logger.info(f"SPIKE: transaction abandoned: {exc}", also_console=True)
            outcome = None
        finally:
            self.in_transaction = False

        if outcome is not None:
            self.transactions.append(outcome)
            if outcome["rerun_ok"]:
                if result.assign:
                    BuiltIn().set_local_variable(result.assign[0], outcome["return_value"])
                result.status = "PASS"
                logger.info(f"SPIKE: healed via {outcome}", also_console=True)

    async def _heal(self, data, result):
        """Runs on the healer loop; all RF access marshalled to the main thread."""
        bi = MainThreadProxy(BuiltIn(), self.runtime)

        async def fake_llm():
            await asyncio.sleep(0.7)
            return "corrected-value"

        async def read_rf_state():
            return await asyncio.to_thread(bi.get_variable_value, "${TEST NAME}")

        # parallel async work on the loop + marshalled RF read
        corrected, test_name = await asyncio.gather(fake_llm(), read_rf_state())

        def rerun():
            value = BuiltIn().run_keyword("Set Variable", corrected)
            BuiltIn().run_keyword("Should Be Equal", corrected, "corrected-value")
            return value

        try:
            return_value = await asyncio.to_thread(self.runtime.call_on_main, rerun)
            rerun_ok = True
        except Exception as exc:  # noqa: BLE001
            return_value, rerun_ok = repr(exc), False

        return {
            "test_name": test_name,
            "return_value": return_value,
            "rerun_ok": rerun_ok,
        }

    def _handle_hang(self, data, result):
        async def hang():
            await asyncio.sleep(3600)

        self.in_transaction = True
        try:
            self.runtime.run_transaction(hang(), timeout_seconds=0.5)
            logger.info("SPIKE: hang transaction returned unexpectedly", also_console=True)
        except TimeoutError:
            logger.info("SPIKE: hang transaction abandoned as designed", also_console=True)
            result.message = "abandoned-as-designed"
        finally:
            self.in_transaction = False

    def close(self):
        self.runtime.shutdown()
