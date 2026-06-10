"""Fix application: AST transformers, unified patches, tiered safety.

Tier 1: healed copies + a git-appliable unified `.patch` (always safe).
Tier 2: in-place edit — refused on a dirty git tree, end-of-run only,
re-parse validated, idempotent. `shared` blast radius never auto-applies.
"""

from __future__ import annotations

import difflib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from robot.api import get_model, get_resource_model
from robot.api.parsing import ModelTransformer

from .resolve import ResolvedFix


class LocatorTokenReplacer(ModelTransformer):
    """Replace one argument token value at a specific line."""

    def __init__(self, lineno: int | None, old_value: str, new_value: str):
        super().__init__()
        self.lineno = lineno
        self.old_value = old_value
        self.new_value = new_value
        self.changed = 0

    def visit_KeywordCall(self, node):
        for token in node.tokens:
            if token.type == "ARGUMENT" and token.value == self.old_value:
                if self.lineno is None or token.lineno == self.lineno:
                    token.value = self.new_value
                    self.changed += 1
        return node


class VariableValueReplacer(ModelTransformer):
    """Replace the value of one ${variable} definition."""

    def __init__(self, variable_name: str, old_value: str, new_value: str):
        super().__init__()
        self.marker = "${" + variable_name + "}"
        self.old_value = old_value
        self.new_value = new_value
        self.changed = 0

    def visit_Variable(self, node):
        if node.name == self.marker:
            for token in node.tokens:
                if token.type == "ARGUMENT" and token.value == self.old_value:
                    token.value = self.new_value
                    self.changed += 1
        return node


@dataclass
class FileChange:
    path: str
    original: str
    healed: str

    @property
    def changed(self) -> bool:
        return self.original != self.healed


@dataclass
class ApplyResult:
    changes: list[FileChange] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # human-readable reasons

    @property
    def changed_files(self) -> list[str]:
        return [c.path for c in self.changes if c.changed]


def _parse_path(path: Path):
    return get_resource_model(str(path)) if path.suffix == ".resource" else get_model(str(path))


def synthesize_changes(fixes: list[ResolvedFix]) -> ApplyResult:
    """Compute healed file contents for a set of resolved fixes (no writes)."""
    result = ApplyResult()
    healed_texts: dict[str, str] = {}

    def current_model(path: Path):
        # chain edits to the same file by re-parsing the healed text
        import tempfile

        if str(path) in healed_texts:
            with tempfile.NamedTemporaryFile(
                "w", suffix=path.suffix, delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(healed_texts[str(path)])
            return _parse_path(Path(tmp.name))
        return _parse_path(path)

    for fix in fixes:
        if fix.kind == "unresolved":
            result.skipped.append(f"{fix.file}:{fix.lineno}: origin could not be resolved")
            continue
        targets: list[tuple[Path, ModelTransformer]] = []
        if fix.kind == "literal":
            targets.append((Path(fix.file), LocatorTokenReplacer(fix.lineno, fix.old_token, fix.new_token)))
        else:
            targets.append(
                (
                    Path(fix.variable_file),
                    VariableValueReplacer(fix.variable_name, fix.variable_old_value, fix.variable_new_value),
                )
            )
        for path, transformer in targets:
            model = current_model(path)
            transformer.visit(model)
            if not getattr(transformer, "changed", 0):
                result.skipped.append(f"{path}: nothing to change (already applied?)")
                continue
            import tempfile

            with tempfile.NamedTemporaryFile("w", suffix=path.suffix, delete=False, encoding="utf-8") as tmp:
                out_path = tmp.name
            model.save(out_path)
            healed = Path(out_path).read_text(encoding="utf-8")
            # re-parse validation: a healed file must still be valid RF syntax
            _parse_path(Path(out_path))
            healed_texts[str(path)] = healed
            result.changes.append(
                FileChange(path=str(path), original=path.read_text(encoding="utf-8"), healed=healed)
            )
    # collapse multiple changes per file, keep the last healed text
    collapsed: dict[str, FileChange] = {}
    for change in result.changes:
        if change.path in collapsed:
            collapsed[change.path] = FileChange(
                path=change.path, original=collapsed[change.path].original, healed=change.healed
            )
        else:
            collapsed[change.path] = change
    result.changes = list(collapsed.values())
    return result


def unified_patch(result: ApplyResult, repo_root: str | Path | None = None) -> str:
    """git-appliable unified diff for all changed files."""
    chunks = []
    for change in result.changes:
        if not change.changed:
            continue
        rel = change.path
        if repo_root:
            try:
                rel = str(Path(change.path).resolve().relative_to(Path(repo_root).resolve()))
            except ValueError:
                pass
        diff = difflib.unified_diff(
            change.original.splitlines(keepends=True),
            change.healed.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
        chunks.append("".join(diff))
    return "".join(chunks)


def write_healed_copies(result: ApplyResult, out_dir: str | Path) -> list[Path]:
    out_dir = Path(out_dir)
    written = []
    for change in result.changes:
        if not change.changed:
            continue
        source = Path(change.path)
        target = out_dir / source.parent.name / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(change.healed, encoding="utf-8")
        written.append(target)
    return written


def _dirty_files(paths: list[str]) -> list[str]:
    dirty = []
    for path in paths:
        try:
            out = subprocess.run(
                ["git", "status", "--porcelain", "--", Path(path).name],
                cwd=str(Path(path).parent),
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            continue  # not a repo -> treat as clean (nothing to clash with)
        if out.returncode == 0 and out.stdout.strip():
            dirty.append(path)
    return dirty


def apply_in_place(result: ApplyResult, *, force: bool = False) -> tuple[list[str], list[str]]:
    """Tier 2: write healed contents over the originals.

    Refuses files with uncommitted git changes unless `force`. Returns
    (written, refused).
    """
    candidates = [c for c in result.changes if c.changed]
    dirty = set() if force else set(_dirty_files([c.path for c in candidates]))
    written, refused = [], []
    for change in candidates:
        if change.path in dirty:
            refused.append(change.path)
            continue
        Path(change.path).write_text(change.healed, encoding="utf-8")
        written.append(change.path)
    return written, refused
