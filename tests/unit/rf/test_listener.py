"""Listener qualification and shim mapping (RF-free where possible)."""

import warnings
from types import SimpleNamespace

import pytest

from heal.core.settings import HealSettings
from heal.rf.listener import SKIP_PARENT_KEYWORDS, HealListener


def make_listener(**kwargs) -> HealListener:
    return HealListener(settings=HealSettings(_env_file=None, model="openai:gpt-4.1-mini", **kwargs))


def kw(failed=True, owner="Browser", parent_name=None):
    data = SimpleNamespace(parent=SimpleNamespace(name=parent_name), args=["id=x"], lineno=1, source=None)
    result = SimpleNamespace(failed=failed, owner=owner, name="Click", assign=[], message="boom")
    return data, result


@pytest.fixture(autouse=True)
def fake_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_qualifies_failed_browser_keyword():
    listener = make_listener()
    assert listener._qualifies(*kw())


def test_skips_passed_and_foreign_libraries():
    listener = make_listener()
    assert not listener._qualifies(*kw(failed=False))
    assert not listener._qualifies(*kw(owner="DatabaseLibrary"))
    assert not listener._qualifies(*kw(owner=None))


@pytest.mark.parametrize("parent", SKIP_PARENT_KEYWORDS)
def test_skips_expected_failure_wrappers(parent):
    listener = make_listener()
    assert not listener._qualifies(*kw(parent_name=parent))


def test_skips_while_in_transaction():
    listener = make_listener()
    listener._in_transaction = True
    assert not listener._qualifies(*kw())


def test_disabled_listener_never_qualifies():
    listener = make_listener(enabled=False)
    assert not listener._qualifies(*kw())


def test_shim_maps_legacy_kwargs_with_deprecation():
    import SelfHealing as shim_module

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # provide a model so AgentRuntime construction inside is satisfied lazily
        import os

        os.environ["HEAL_MODEL"] = "openai:gpt-4.1-mini"
        try:
            shim = shim_module.SelfHealing(fix="retry", heal_assertions=True)
        finally:
            del os.environ["HEAL_MODEL"]
    assert isinstance(shim, HealListener)
    assert shim.settings.heal_assertions is True
    assert any("deprecated" in str(w.message) for w in caught)


def test_shim_defaults_emit_single_deprecation_only():
    import SelfHealing as shim_module

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        shim_module.SelfHealing()
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1  # the library-level one; no kwarg noise


def test_greedy_fix_skipped_inside_expected_failure_wrappers():
    listener = make_listener()
    listener.fixed_locators["id=broken"] = "css=#fixed"
    data = SimpleNamespace(
        parent=SimpleNamespace(name="Run Keyword And Return Status"),
        args=["id=broken"], lineno=1, source=None,
    )
    result = SimpleNamespace(failed=False, owner="Browser", name="Fill Text", assign=[], args=["id=broken"])
    listener._apply_known_fix(data, result)
    assert data.args == ["id=broken"]  # untouched inside the wrapper


def make_history_with_fix(tmp_path, source="/suites/login.robot", broken="id=old", healed="css=#new"):
    from heal.report.history import HealHistory

    from ..report.test_store_and_reports import make_event

    history = HealHistory(tmp_path / "history.sqlite")
    event = make_event("h1", healed=healed, source=source)
    event.context.failed_locator = broken
    history.record([event])
    return tmp_path / "history.sqlite"


class GreedyFakeDriver:
    def __init__(self, counts):
        self.counts = counts

    def count(self, locator):
        return self.counts.get(locator, 0)


def warm_listener(tmp_path, counts, **settings):
    db = make_history_with_fix(tmp_path)
    listener = HealListener(
        settings=HealSettings(_env_file=None, model="openai:gpt-4.1-mini", history_db=str(db), **settings)
    )
    listener._driver_for = lambda owner: GreedyFakeDriver(counts)
    listener._variable = lambda name: "T"
    return listener


def kw_data(source="/suites/login.robot", args=("id=old",)):
    data = SimpleNamespace(parent=SimpleNamespace(name=None), args=list(args), lineno=5, source=source)
    result = SimpleNamespace(failed=False, owner="Browser", name="Click", assign=[], args=list(args))
    return data, result


def test_warm_start_swaps_and_records_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr("robot.libraries.BuiltIn.BuiltIn.replace_variables", lambda self, v: v, raising=False)
    listener = warm_listener(tmp_path, {"id=old": 0, "css=#new": 1})
    data, result = kw_data()
    listener._apply_known_fix(data, result)
    assert data.args[0] == "css=#new"
    assert len(listener.events) == 1
    event = listener.events[0]
    assert event.event_id.startswith("warm-")
    assert event.outcome.attempts[0].action.params["origin"] == "history"
    assert "history" in event.outcome.detail


def test_warm_start_stale_mapping_falls_through(tmp_path, monkeypatch):
    monkeypatch.setattr("robot.libraries.BuiltIn.BuiltIn.replace_variables", lambda self, v: v, raising=False)
    # healed locator no longer on the page -> no swap, no event
    listener = warm_listener(tmp_path, {"id=old": 0, "css=#new": 0})
    data, result = kw_data()
    listener._apply_known_fix(data, result)
    assert data.args[0] == "id=old"
    assert listener.events == []


def test_warm_start_scoped_to_source_file(tmp_path, monkeypatch):
    monkeypatch.setattr("robot.libraries.BuiltIn.BuiltIn.replace_variables", lambda self, v: v, raising=False)
    listener = warm_listener(tmp_path, {"id=old": 0, "css=#new": 1})
    data, result = kw_data(source="/other/suite.robot")
    listener._apply_known_fix(data, result)
    assert data.args[0] == "id=old"  # mapping belongs to login.robot


def test_warm_start_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr("robot.libraries.BuiltIn.BuiltIn.replace_variables", lambda self, v: v, raising=False)
    listener = warm_listener(tmp_path, {"id=old": 0, "css=#new": 1}, warm_start=False)
    data, result = kw_data()
    listener._apply_known_fix(data, result)
    assert data.args[0] == "id=old"
    assert listener.warm_fixes == {}


def test_warm_event_keeps_mapping_alive_in_history(tmp_path, monkeypatch):
    """Reused mappings must re-record with the broken locator (renewal)."""
    monkeypatch.setattr("robot.libraries.BuiltIn.BuiltIn.replace_variables", lambda self, v: v, raising=False)
    listener = warm_listener(tmp_path, {"id=old": 0, "css=#new": 1})
    data, result = kw_data()
    listener._apply_known_fix(data, result)
    event = listener.events[0]
    assert event.context is not None
    assert event.context.failed_locator == "id=old"

    from heal.report.history import HealHistory

    history = HealHistory(tmp_path / "renewed.sqlite")
    history.record([event])
    mappings = history.recent_mappings()
    assert ("/suites/login.robot", "id=old", "css=#new") in mappings


def test_heal_entry_point_is_a_valid_listener():
    """`Library    Heal` must resolve to a working listener (docs use this form)."""
    import Heal

    assert issubclass(Heal.Heal, HealListener)
    # RF requires the module to expose a class matching the module name
    assert Heal.Heal.__name__ == "Heal"
    instance = Heal.Heal()
    assert instance.ROBOT_LISTENER_API_VERSION == 3
    assert instance.ROBOT_LIBRARY_SCOPE == "GLOBAL"
    assert instance.ROBOT_LIBRARY_LISTENER is instance  # acts as its own listener
