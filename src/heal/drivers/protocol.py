"""SessionDriver: the capability surface the engine uses to talk to a live session.

One protocol, multiple implementations (Browser, Appium). Toolsets for agents
and the MCP server wrap this same protocol — write once, serve all surfaces.
All implementations are expected to be called from the RF main thread; the
engine marshals calls there (see design D4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ElementInfo:
    """Inspection snapshot of one element."""

    locator: str
    tag_name: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    inner_text: str = ""
    visible: bool = False
    in_viewport: bool | None = None
    clickable: bool | None = None


@runtime_checkable
class SessionDriver(Protocol):
    """Query / inspect / act primitives over a live automation session."""

    #: RF library name this driver handles (e.g. "Browser", "AppiumLibrary").
    library_name: str

    # ----- query -----
    def count(self, locator: str) -> int:
        """Number of elements matching the locator (0 on invalid locator)."""
        ...

    def is_visible(self, locator: str) -> bool: ...

    def is_in_viewport(self, locator: str) -> bool | None:
        """None when the driver cannot determine viewport intersection."""
        ...

    # ----- inspect -----
    def get_page_source(self) -> str:
        """Full page source (piercing shadow DOM where supported)."""
        ...

    def get_simplified_dom(self) -> str:
        """Curated, prompt-friendly DOM excerpt."""
        ...

    def get_element_info(self, locator: str) -> ElementInfo: ...

    def is_page_ready(self) -> bool: ...

    def open_dialog_locator(self) -> str | None:
        """Locator/marker of an open dialog/overlay, or None."""
        ...

    def take_screenshot(self) -> bytes | None:
        """PNG bytes, or None when unsupported/headless-blocked."""
        ...

    # ----- act -----
    def scroll_into_view(self, locator: str) -> bool:
        """Bring the element into the viewport; True when it ended up visible."""
        ...

    def click(self, locator: str) -> None: ...

    def wait_until_ready(self, timeout_seconds: float) -> bool:
        """Wait for page-ready; True when ready within the timeout."""
        ...
