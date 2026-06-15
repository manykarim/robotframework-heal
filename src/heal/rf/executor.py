"""Transaction runtime: persistent healer event loop + main-thread call marshalling.

Design D4: pydantic-ai needs a real event loop; RF listener callbacks are
synchronous; Browser/Appium instances are only safe on the RF main thread.

    RF MAIN THREAD                        HEALER THREAD (one loop, run-long)
    run_transaction(coro, timeout)        coro awaits agents / evidence
      submit ─────────────────────────►   needs a driver/RF call?
      serve MainCall queue:                 call_on_main(fn) enqueues + blocks
        execute fn, deliver result ────►    ...continues with result
      until coro done or deadline ◄──────  returns HealEvent

`call_on_main` is callable from any non-main thread (plugins run inside
`asyncio.to_thread` workers). When invoked on the main thread directly (CLI,
tests, single-threaded surfaces) it just executes the function.

Deadlock safety: `run_transaction` serves the queue until the transaction
finishes or `timeout + grace` elapses; on abandonment every pending and
subsequent MainCall is failed with `TransactionAbandoned`, which unblocks any
worker thread still waiting and lets the healer loop finish in the background.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

ABANDON_GRACE_SECONDS = 10.0
_SERVE_POLL_SECONDS = 0.05


class TransactionAbandoned(RuntimeError):
    """The main thread stopped serving this transaction (timeout)."""


@dataclass
class _MainCall:
    fn: Callable[..., Any]
    args: tuple
    kwargs: dict
    done: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: BaseException | None = None

    def execute(self) -> None:
        try:
            self.result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:  # delivered to the caller, never swallowed
            self.error = exc
        finally:
            self.done.set()

    def fail(self, exc: BaseException) -> None:
        self.error = exc
        self.done.set()

    def wait(self) -> Any:
        self.done.wait()
        if self.error is not None:
            raise self.error
        return self.result


class TransactionRuntime:
    """One per process. Hosts the healer loop; marshals calls to the main thread."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._calls: queue.Queue[_MainCall] = queue.Queue()
        self._abandoned = threading.Event()
        self._main_thread = threading.current_thread()
        self._lock = threading.Lock()

    # ----------------------------------------------------------------- lifecycle

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                self._thread = threading.Thread(
                    target=self._run_loop, name="heal-engine", daemon=True
                )
                self._thread.start()
        self._loop_ready.wait()
        assert self._loop is not None
        return self._loop

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()
        loop.run_forever()

    def shutdown(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._loop = None
            self._loop_ready.clear()

    # ----------------------------------------------------------------- main side

    def run_transaction(self, coro: Coroutine, timeout_seconds: float) -> Any:
        """Run `coro` on the healer loop, serving main-thread calls meanwhile.

        Returns the coroutine result; raises TimeoutError on abandonment.
        Must be called on the thread whose calls the transaction marshals
        (the RF main thread under the listener).
        """
        loop = self._ensure_loop()
        self._abandoned.clear()
        self._main_thread = threading.current_thread()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        hard_deadline = time.monotonic() + timeout_seconds + ABANDON_GRACE_SECONDS
        while True:
            try:
                call = self._calls.get(timeout=_SERVE_POLL_SECONDS)
            except queue.Empty:
                call = None
            if call is not None:
                call.execute()
            if future.done():
                return future.result()
            if time.monotonic() >= hard_deadline:
                self._abandon(future)
                raise TimeoutError(
                    f"healing transaction abandoned after {timeout_seconds + ABANDON_GRACE_SECONDS:.0f}s"
                )

    def _abandon(self, future: concurrent.futures.Future) -> None:
        self._abandoned.set()
        future.cancel()
        while True:
            try:
                call = self._calls.get_nowait()
            except queue.Empty:
                break
            call.fail(TransactionAbandoned("main thread stopped serving"))

    # --------------------------------------------------------------- worker side

    def call_on_main(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute `fn` on the serving (RF main) thread and return its result."""
        if threading.current_thread() is self._main_thread:
            return fn(*args, **kwargs)
        if self._abandoned.is_set():
            raise TransactionAbandoned("transaction already abandoned")
        call = _MainCall(fn=fn, args=args, kwargs=kwargs)
        self._calls.put(call)
        return call.wait()


class MainThreadProxy:
    """Wraps an object so every method call is marshalled via the runtime.

    Used to hand SessionDrivers to plugins: plugin code calls driver methods
    synchronously (from to_thread workers); the proxy reroutes each call to
    the RF main thread.
    """

    def __init__(self, target: Any, runtime: TransactionRuntime):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_runtime", runtime)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr
        runtime = self._runtime

        def marshalled(*args: Any, **kwargs: Any) -> Any:
            return runtime.call_on_main(attr, *args, **kwargs)

        return marshalled
