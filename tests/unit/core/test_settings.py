import warnings

import pytest

from heal.core.settings import (
    FixTier,
    HealSettings,
    OutputMode,
    settings_from_legacy_kwargs,
)


@pytest.fixture()
def clean_env(monkeypatch):
    # isolate from process env (tests pass _env_file=None to skip .env)
    for var in list(__import__("os").environ):
        if var.startswith("HEAL_"):
            monkeypatch.delenv(var)
    return monkeypatch


def test_defaults(clean_env):
    s = HealSettings(_env_file=None)
    assert s.enabled is True
    assert s.heal_assertions is False
    assert s.form_fill is False
    assert s.fix_tier is FixTier.REPORT
    assert s.max_failure_seconds == 60.0


def test_env_prefix_loading(clean_env):
    clean_env.setenv("HEAL_MODEL", "MiniMax-M2.5")
    clean_env.setenv("HEAL_BASE_URL", "https://api.minimax.io/v1")
    clean_env.setenv("HEAL_LOCATOR_MODEL", "qwen3-14b")
    clean_env.setenv("HEAL_LOCATOR_OUTPUT_MODE", "prompted")
    clean_env.setenv("HEAL_MAX_FAILURE_SECONDS", "30")
    s = HealSettings(_env_file=None)
    assert s.model == "MiniMax-M2.5"
    assert s.max_failure_seconds == 30.0

    locator = s.role_config("locator")
    assert locator.model == "qwen3-14b"
    assert locator.base_url == "https://api.minimax.io/v1"  # fallback to default
    assert locator.output_mode is OutputMode.PROMPTED

    triage = s.role_config("triage")
    assert triage.model == "MiniMax-M2.5"  # fallback
    assert triage.output_mode is OutputMode.AUTO


def test_role_config_rejects_unknown_role(clean_env):
    with pytest.raises(ValueError, match="Unknown agent role"):
        HealSettings(_env_file=None).role_config("orchestrator")


def test_legacy_kwargs_mapped_with_deprecation(clean_env):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        s = settings_from_legacy_kwargs(heal_assertions=True, locator_db_file="db.json")
    assert s.heal_assertions is True
    assert s.history_db == "db.json"
    assert all(issubclass(w.category, DeprecationWarning) for w in caught)
    assert len(caught) == 2


def test_legacy_dropped_kwargs_ignored_with_warning(clean_env):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        s = settings_from_legacy_kwargs(fix="realtime", use_locator_db=True)
    assert isinstance(s, HealSettings)
    assert len(caught) == 2
    assert "no effect" in str(caught[0].message)


def test_legacy_unknown_kwarg_raises(clean_env):
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        settings_from_legacy_kwargs(bogus=1)
