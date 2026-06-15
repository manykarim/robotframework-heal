"""RF-backed HealSession: driver proxied to the main thread, rerun via BuiltIn."""

from __future__ import annotations

from typing import Any

from robot.libraries.BuiltIn import BuiltIn

from ..core.schemas import KeywordCall
from .executor import MainThreadProxy, TransactionRuntime


class RfHealSession:
    """HealSession implementation used under the listener.

    Plugins call `driver` methods and `rerun_keyword` from healer-loop worker
    threads; everything is marshalled to the RF main thread.
    """

    def __init__(self, driver, runtime: TransactionRuntime):
        self._runtime = runtime
        self.driver = MainThreadProxy(driver, runtime) if driver is not None else None
        #: actual (non-serialized) return value of the last successful rerun,
        #: used by the listener for `${var} =` assignment after a heal
        self.last_return_value: Any = None

    def rerun_keyword(self, keyword: KeywordCall, *, locator_override: str | None = None) -> Any:
        def _rerun():
            args = list(keyword.args)
            if locator_override is not None and args:
                args[0] = locator_override
            return BuiltIn().run_keyword(keyword.name, *args)

        value = self._runtime.call_on_main(_rerun)
        self.last_return_value = value
        return value
