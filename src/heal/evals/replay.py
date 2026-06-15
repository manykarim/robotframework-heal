"""Replay a serialized FailureContext without a browser.

`ReplayDriver` answers SessionDriver queries from the recorded DOM excerpt,
so triage and locator healing can run (and be measured) against any model
with no automation stack — the basis of the failure-class × model-tier
compatibility matrix.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..core.evidence import ContextBuilder
from ..core.schemas import EvidenceKind, FailureContext


class ReplayDriver:
    """SessionDriver over a recorded DOM excerpt (read-only queries)."""

    dom_covers_viewport_only = False

    def __init__(self, ctx: FailureContext):
        dom = ctx.evidence_of(EvidenceKind.DOM_EXCERPT)
        self._dom = dom.excerpt if dom else ""
        self._soup = BeautifulSoup(self._dom, "html.parser")

    def _select(self, locator: str):
        css = locator
        for prefix in ("css=", "id="):
            if locator.startswith(prefix):
                css = ("#" + locator[3:]) if prefix == "id=" else locator[4:]
                break
        else:
            if locator.startswith("xpath=") or locator.startswith("//"):
                return []  # xpath not supported in replay; counts as no match
        try:
            return self._soup.select(css)
        except Exception:
            return []

    # ----- query -----
    def count(self, locator: str) -> int:
        return len(self._select(locator))

    def is_visible(self, locator: str) -> bool:
        return self.count(locator) > 0

    def is_in_viewport(self, locator: str) -> bool | None:
        return True if self.count(locator) > 0 else None

    # ----- inspect -----
    def get_page_source(self) -> str:
        return self._dom

    def get_simplified_dom(self) -> str:
        return self._dom

    def get_element_info(self, locator: str):
        from ..drivers.protocol import ElementInfo

        return ElementInfo(locator=locator, visible=self.is_visible(locator))

    def is_page_ready(self) -> bool:
        return True

    def open_dialog_locator(self) -> str | None:
        return "dialog[open]" if self._soup.find("dialog", {"open": True}) else None

    def find_dismiss_controls(self) -> list[str]:
        return []

    def find_form_issues(self) -> list[str]:
        return []

    def take_screenshot(self) -> bytes | None:
        return None

    # ----- act (no-ops in replay) -----
    def scroll_into_view(self, locator: str) -> bool:
        return self.count(locator) > 0

    def click(self, locator: str) -> None:
        if self.count(locator) == 0:
            raise AssertionError(f"no element for {locator!r}")

    def wait_until_ready(self, timeout_seconds: float) -> bool:
        return True


class ReplaySession:
    """HealSession over a ReplayDriver; reruns succeed when the locator resolves."""

    def __init__(self, ctx: FailureContext):
        self.driver = ReplayDriver(ctx)
        self.reruns: list[tuple[str, str | None]] = []

    def rerun_keyword(self, keyword, *, locator_override=None):
        target = locator_override or (keyword.args[0] if keyword.args else None)
        self.reruns.append((keyword.name, locator_override))
        if target and self.driver.count(target) == 0:
            raise AssertionError(f"replay: {target!r} matches nothing")
        return "replayed"


def builder_from_context(ctx: FailureContext) -> ContextBuilder:
    """Rebuild a ContextBuilder whose evidence is the recorded evidence."""
    builder = ContextBuilder(
        keyword=ctx.keyword,
        error_message=ctx.error_message,
        test_name=ctx.test_name,
        suite_name=ctx.suite_name,
        failed_locator=ctx.failed_locator,
        driver=None,
    )
    builder._evidence = dict(ctx.evidence)  # noqa: SLF001 - replay injects recorded evidence
    builder._attempted = {k for k in ctx.evidence}  # noqa: SLF001
    return builder


def load_fixture(path) -> FailureContext:
    from pathlib import Path

    return FailureContext.model_validate_json(Path(path).read_text(encoding="utf-8"))
