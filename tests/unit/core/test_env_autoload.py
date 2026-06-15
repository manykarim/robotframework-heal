"""Automatic .env loading: nearest .env wins over pre-set environment vars."""

import os

from heal.core.settings import HealSettings, autoload_env


def test_dotenv_overrides_process_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "HEAL_MODEL=from-dotenv\nMY_PROVIDER_KEY=secret-from-dotenv\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HEAL_MODEL", "from-shell")
    monkeypatch.setenv("MY_PROVIDER_KEY", "stale-shell-value")

    settings = HealSettings()
    assert settings.model == "from-dotenv"  # .env overrides the shell
    # non-HEAL keys are exported too (provider SDKs read them from os.environ)
    assert os.environ["MY_PROVIDER_KEY"] == "secret-from-dotenv"


def test_explicit_env_file_none_skips_autoload(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("HEAL_MODEL=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HEAL_MODEL", "from-shell")

    settings = HealSettings(_env_file=None)
    assert settings.model == "from-shell"


def test_autoload_without_env_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert autoload_env() is None  # no .env anywhere up the tree from tmp
    settings = HealSettings()  # must not raise
    assert isinstance(settings, HealSettings)
