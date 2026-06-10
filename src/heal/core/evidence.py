"""Lazy, cost-tagged evidence collection into an immutable FailureContext.

Collectors run only when a pipeline tier requests their kind; results are
cached for the transaction. Excerpts are bounded — prompts never receive
whole files or raw DOM trees. Failure to collect yields *absent evidence*,
never an exception out of the builder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .gitinfo import file_git_info
from .schemas import Evidence, EvidenceKind, FailureContext, KeywordCall

MAX_DOM_CHARS = 30_000
SOURCE_CONTEXT_LINES = 10


class ContextBuilder:
    """Assembles the FailureContext for one transaction, collecting on demand.

    `driver` is duck-typed against heal.drivers.protocol.SessionDriver (kept
    duck-typed here so core stays import-clean of driver packages).
    """

    def __init__(
        self,
        *,
        keyword: KeywordCall,
        error_message: str,
        test_name: str = "",
        suite_name: str = "",
        failed_locator: str | None = None,
        driver=None,
        artifact_dir: str | Path | None = None,
    ) -> None:
        self._driver = driver
        self._artifact_dir = Path(artifact_dir) if artifact_dir else None
        self._evidence: dict[str, Evidence] = {}
        self._attempted: set[str] = set()
        self._base = FailureContext(
            keyword=keyword,
            error_message=error_message,
            test_name=test_name,
            suite_name=suite_name,
            failed_locator=failed_locator,
        )
        self._collectors: dict[EvidenceKind, Callable[[], Evidence | None]] = {
            EvidenceKind.DOM_EXCERPT: self._collect_dom,
            EvidenceKind.SCREENSHOT: self._collect_screenshot,
            EvidenceKind.SOURCE_EXCERPT: self._collect_source_excerpt,
            EvidenceKind.GIT_HISTORY: self._collect_git_history,
        }

    # ------------------------------------------------------------------ public

    def ensure(self, *kinds: EvidenceKind) -> None:
        """Collect the given evidence kinds (no-op for cached/failed ones)."""
        for kind in kinds:
            if kind.value in self._attempted:
                continue
            self._attempted.add(kind.value)
            collector = self._collectors.get(kind)
            if collector is None:
                continue
            try:
                evidence = collector()
            except Exception:
                evidence = None
            if evidence is not None:
                self._evidence[kind.value] = evidence

    def context(self, *kinds: EvidenceKind) -> FailureContext:
        """Return the immutable context, ensuring `kinds` are collected first."""
        self.ensure(*kinds)
        return self._base.model_copy(update={"evidence": dict(self._evidence)})

    # -------------------------------------------------------------- collectors

    def _collect_dom(self) -> Evidence | None:
        if self._driver is None:
            return None
        dom = self._driver.get_simplified_dom()
        if not dom:
            return None
        truncated = len(dom) > MAX_DOM_CHARS
        return Evidence(
            kind=EvidenceKind.DOM_EXCERPT,
            summary="simplified DOM" + (" (truncated)" if truncated else ""),
            excerpt=dom[:MAX_DOM_CHARS],
        )

    def _collect_screenshot(self) -> Evidence | None:
        if self._driver is None or self._artifact_dir is None:
            return None
        png = self._driver.take_screenshot()
        if not png:
            return None
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        name = f"failure-{abs(hash((self._base.test_name, self._base.keyword.lineno))) % 10**8}.png"
        path = self._artifact_dir / name
        path.write_bytes(png)
        return Evidence(kind=EvidenceKind.SCREENSHOT, summary="screenshot at failure", path=str(path))

    def _collect_source_excerpt(self) -> Evidence | None:
        source, lineno = self._base.keyword.source, self._base.keyword.lineno
        if not source or not lineno:
            return None
        path = Path(source)
        if not path.is_file():
            return None
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        start = max(0, lineno - 1 - SOURCE_CONTEXT_LINES)
        end = min(len(lines), lineno + SOURCE_CONTEXT_LINES)
        numbered = [
            f"{'>> ' if i + 1 == lineno else '   '}{i + 1}: {line}"
            for i, line in enumerate(lines[start:end], start=start)
        ]
        return Evidence(
            kind=EvidenceKind.SOURCE_EXCERPT,
            summary=f"{path.name}:{lineno} ±{SOURCE_CONTEXT_LINES} lines",
            excerpt="\n".join(numbered),
        )

    def _collect_git_history(self) -> Evidence | None:
        source = self._base.keyword.source
        if not source:
            return None
        info = file_git_info(source)
        if not info.available:
            return None
        return Evidence(
            kind=EvidenceKind.GIT_HISTORY,
            summary=f"test file last modified {info.last_modified}",
            excerpt=info.summary(),
        )
