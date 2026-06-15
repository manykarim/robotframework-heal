"""The generated config/CLI reference must cover the whole user-facing surface."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "docs"))

import _refgen  # noqa: E402

from heal.cli.main import app as cli_app  # noqa: E402
from heal.core.settings import HealSettings  # noqa: E402


def test_every_setting_in_config_reference():
    text = _refgen.generate_config_reference()
    for name in HealSettings.model_fields:
        assert f"`{_refgen.env_var(name)}`" in text, f"{name} missing from config reference"


def test_enum_settings_list_choices():
    text = _refgen.generate_config_reference()
    # FixTier choices
    assert "`report`" in text and "`patch`" in text and "`in-place`" in text
    # OutputMode choices
    assert "`auto`" in text and "`prompted`" in text


def test_constraints_and_defaults_rendered():
    text = _refgen.generate_config_reference()
    assert "`HEAL_MAX_FAILURE_SECONDS`" in text and "> 0" in text
    assert "`60.0`" in text  # its default
    assert "matches `^(selection|generation)$`" in text  # locator_tiers pattern


def test_every_cli_command_in_reference():
    text = _refgen.generate_cli_reference()
    for command in cli_app.registered_commands:
        name = (command.name or command.callback.__name__).replace("_", "-")
        assert f"## `heal {name}`" in text, f"{name} missing from CLI reference"


def test_config_guard_fires_on_missing_description(monkeypatch):
    fields = dict(HealSettings.model_fields)
    victim = next(iter(fields))

    class _NoDesc:
        def __init__(self, field):
            self.__dict__.update({k: getattr(field, k, None) for k in ("annotation", "default", "metadata")})
            self.description = None

    patched = dict(fields)
    patched[victim] = _NoDesc(fields[victim])
    monkeypatch.setattr(HealSettings, "model_fields", patched)
    with pytest.raises(SystemExit, match="without a description"):
        _refgen.generate_config_reference()
