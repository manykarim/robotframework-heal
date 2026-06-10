"""Bounded, cached git context for test sources (feeds RCA).

"This locator's line last changed 14 months ago" is a strong causality hint
for distinguishing test-outdated from application-changed. Everything here is
best-effort: no repo, no git, or timeouts simply yield None/empty.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_GIT_TIMEOUT = 5.0
_MAX_COMMITS = 3


@dataclass(frozen=True)
class FileGitInfo:
    last_modified: str = ""  # ISO date of the last commit touching the file
    recent_commits: tuple[str, ...] = field(default_factory=tuple)

    @property
    def available(self) -> bool:
        return bool(self.last_modified or self.recent_commits)

    def summary(self) -> str:
        if not self.available:
            return ""
        lines = []
        if self.last_modified:
            lines.append(f"last modified: {self.last_modified}")
        lines.extend(self.recent_commits)
        return "\n".join(lines)


def _git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


@lru_cache(maxsize=256)
def file_git_info(source: str) -> FileGitInfo:
    """Last-modified date and recent history for one file (cached per path)."""
    path = Path(source)
    if not path.is_file():
        return FileGitInfo()
    cwd = path.parent
    last = _git(["log", "-1", "--format=%cs", "--", path.name], cwd)
    if last is None:
        return FileGitInfo()
    log = _git(
        ["log", f"-{_MAX_COMMITS}", "--format=%cs %s", "--", path.name],
        cwd,
    )
    commits = tuple(log.splitlines()) if log else ()
    return FileGitInfo(last_modified=last or "", recent_commits=commits)
