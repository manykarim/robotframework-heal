import asyncio
import threading
import time

import pytest

from heal.rf.executor import (
    MainThreadProxy,
    TransactionAbandoned,
    TransactionRuntime,
)


@pytest.fixture()
def runtime():
    rt = TransactionRuntime()
    yield rt
    rt.shutdown()


def test_transaction_with_marshalled_calls(runtime):
    main_thread_calls = []

    def rf_call(value):
        main_thread_calls.append((threading.current_thread().name, value))
        return value * 2

    async def transaction():
        a = await asyncio.to_thread(runtime.call_on_main, rf_call, 21)
        b, c = await asyncio.gather(
            asyncio.to_thread(runtime.call_on_main, rf_call, 1),
            asyncio.sleep(0.05, result="parallel"),
        )
        return a, b, c

    result = runtime.run_transaction(transaction(), timeout_seconds=5)
    assert result == (42, 2, "parallel")
    assert all(thread == threading.current_thread().name for thread, _ in main_thread_calls)


def test_call_on_main_propagates_exceptions(runtime):
    def boom():
        raise ValueError("driver exploded")

    async def transaction():
        try:
            await asyncio.to_thread(runtime.call_on_main, boom)
        except ValueError as exc:
            return f"caught: {exc}"

    assert runtime.run_transaction(transaction(), timeout_seconds=5) == "caught: driver exploded"


def test_call_on_main_direct_when_on_main_thread(runtime):
    assert runtime.call_on_main(lambda: threading.current_thread()) is threading.current_thread()


def test_timeout_abandons_and_unblocks(runtime, monkeypatch):
    monkeypatch.setattr("heal.rf.executor.ABANDON_GRACE_SECONDS", 0.2)

    async def hang():
        await asyncio.sleep(3600)

    start = time.monotonic()
    with pytest.raises(TimeoutError, match="abandoned"):
        runtime.run_transaction(hang(), timeout_seconds=0.2)
    assert time.monotonic() - start < 5

    # runtime stays usable for the next transaction
    async def quick():
        return "next"

    assert runtime.run_transaction(quick(), timeout_seconds=5) == "next"


def test_abandoned_pending_calls_fail_not_deadlock(runtime, monkeypatch):
    monkeypatch.setattr("heal.rf.executor.ABANDON_GRACE_SECONDS", 0.2)
    worker_error = []

    async def transaction():
        def slow_then_call():
            time.sleep(1.0)  # survives past abandonment
            try:
                runtime.call_on_main(lambda: "never")
            except TransactionAbandoned as exc:
                worker_error.append(exc)
                raise

        await asyncio.to_thread(slow_then_call)

    with pytest.raises(TimeoutError):
        runtime.run_transaction(transaction(), timeout_seconds=0.1)
    time.sleep(1.2)  # let the worker hit the abandoned path
    assert worker_error, "late call_on_main must fail fast, not block forever"


def test_main_thread_proxy_marshals_methods(runtime):
    class Driver:
        def __init__(self):
            self.calls = []
            self.library_name = "Fake"

        def count(self, locator):
            self.calls.append(threading.current_thread().name)
            return 7

    driver = Driver()
    proxy = MainThreadProxy(driver, runtime)

    async def transaction():
        return await asyncio.to_thread(proxy.count, "id=x")

    assert runtime.run_transaction(transaction(), timeout_seconds=5) == 7
    assert driver.calls == [threading.current_thread().name]
    assert proxy.library_name == "Fake"  # non-callables pass through
