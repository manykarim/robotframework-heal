"""Deprecated entry point: `SelfHealing` now routes to the `heal` engine.

Existing suites using `Library    SelfHealing    fix=realtime` keep working;
legacy keyword arguments map onto `HEAL_*` settings where semantics match and
emit deprecation warnings. New code should use `heal.rf.HealListener` and
environment-based configuration.
"""

import warnings

from heal.core.settings import settings_from_legacy_kwargs
from heal.rf.listener import HealListener

_LEGACY_DEFAULTS = {
    "fix": "realtime",
    "collect_locator_info": False,
    "use_locator_db": False,
    "use_llm_for_locator_proposals": True,
    "heal_assertions": False,
    "locator_db_file": "locator_db.json",
}


class SelfHealing(HealListener):
    """Backward-compatible listener shim (deprecated; see heal.rf.HealListener)."""

    def __init__(
        self,
        fix="realtime",
        collect_locator_info=False,
        use_locator_db=False,
        use_llm_for_locator_proposals=True,
        heal_assertions=False,
        locator_db_file="locator_db.json",
    ):
        warnings.warn(
            "The 'SelfHealing' library is deprecated; use 'heal.rf.HealListener' "
            "with HEAL_* environment configuration instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        passed = {
            name: value
            for name, value in {
                "fix": fix,
                "collect_locator_info": collect_locator_info,
                "use_locator_db": use_locator_db,
                "use_llm_for_locator_proposals": use_llm_for_locator_proposals,
                "heal_assertions": heal_assertions,
                "locator_db_file": locator_db_file,
            }.items()
            if value != _LEGACY_DEFAULTS[name]
        }
        super().__init__(settings=settings_from_legacy_kwargs(**passed))
