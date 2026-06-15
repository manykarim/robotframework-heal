import threading

from pydantic_ai.usage import RunUsage

from heal.core.ledger import RunLedger
from heal.core.settings import HealSettings


def make_ledger(**kwargs) -> RunLedger:
    return RunLedger(settings=HealSettings(_env_file=None, **kwargs))


def test_transaction_budget_from_settings():
    ledger = make_ledger(max_failure_seconds=30, request_limit=5, max_failure_tokens=1000)
    budget = ledger.begin_transaction()
    assert budget.usage_limits.request_limit == 5
    assert budget.usage_limits.total_tokens_limit == 1000
    assert 0 < budget.remaining_seconds() <= 30
    assert not budget.exhausted()
    assert ledger.transactions == 1


def test_run_budget_breach_degrades():
    ledger = make_ledger(max_run_tokens=1000)
    assert not ledger.run_budget_exhausted()
    ledger.record_usage(RunUsage(requests=2, input_tokens=600, output_tokens=600))
    assert ledger.total_tokens == 1200
    assert ledger.run_budget_exhausted()


def test_record_usage_none_is_noop():
    ledger = make_ledger()
    ledger.record_usage(None)
    assert ledger.total_tokens == 0


def test_outcome_counters():
    ledger = make_ledger()
    for status in ("healed", "healed", "unhealed", "suppressed"):
        ledger.record_outcome(status)
    snap = ledger.snapshot()
    assert (snap["healed"], snap["unhealed"], snap["suppressed"]) == (2, 1, 1)


def test_thread_safety_under_concurrent_updates():
    ledger = make_ledger(max_run_tokens=10_000_000)

    def worker():
        for _ in range(200):
            ledger.record_usage(RunUsage(requests=1, input_tokens=1, output_tokens=1))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert ledger.total_tokens == 8 * 200 * 2
    assert ledger.total_requests == 8 * 200
