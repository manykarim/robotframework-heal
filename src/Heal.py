"""Robot Framework listener entry point — ``Library    Heal``.

A short, idiomatic single-name alias for :class:`heal.rf.HealListener`, so test
suites can write::

    *** Settings ***
    Library    Heal

This is exactly equivalent to ``Library    heal.rf.HealListener``. The legacy
``Library    SelfHealing`` import still works but is deprecated.

Implementation note: this is a top-level *module* (``Heal.py``), not a package,
on purpose — a ``Heal/`` directory would collide with the ``heal/`` package on
case-insensitive filesystems (macOS, Windows). ``Heal.py`` and ``heal/`` are
distinct paths and coexist safely.
"""

from heal.core.settings import HealSettings
from heal.rf.listener import HealListener


class Heal(HealListener):
    """Self-healing Robot Framework listener. Use as ``Library    Heal``."""

    def __init__(self, settings: HealSettings | None = None):
        super().__init__(settings=settings)


__all__ = ["Heal"]
