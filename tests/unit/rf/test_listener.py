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
