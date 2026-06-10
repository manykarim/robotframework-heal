"""Locator-origin resolution and blast-radius analysis over the RF AST.

Given "old locator -> new locator at file:line", determine WHAT must change:
* a literal argument at the call site            -> local change
* a `${VAR}` argument (value == locator)         -> variable definition change
* a `${VAR} suffix` argument                     -> variable and/or suffix change
and WHERE the variable is defined (same file or an imported .resource), plus
every usage site of that variable across the suite tree — a `shared` blast
radius must never be auto-applied.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from robot.api import get_model, get_resource_model
from robot.parsing.model.blocks import File

_VAR_PATTERN = re.compile(r"^\$\{([^}]+)\}(.*)$", re.DOTALL)


@dataclass
class ResolvedFix:
    """What has to change to make a healed locator permanent."""

    kind: str  # "literal" | "variable" | "variable+suffix" | "unresolved"
    file: str  # file containing the token to change (call site for literal)
    lineno: int | None
    old_token: str = ""
    new_token: str = ""
    variable_name: str = ""  # for variable kinds
    variable_file: str = ""  # where the variable is defined
    variable_old_value: str = ""
    variable_new_value: str = ""
    usages: list[tuple[str, int]] = field(default_factory=list)  # (file, lineno)

    @property
    def blast_radius(self) -> str:
        if self.kind == "literal":
            return "local"
        return "shared" if len(self.usages) > 1 else "local"


def _parse(path: str | Path) -> File:
    path = Path(path)
    if path.suffix == ".resource":
        return get_resource_model(str(path))
    return get_model(str(path))


def _iter_keyword_calls(model: File):
    from robot.parsing.model.statements import KeywordCall, TemplateArguments

    for node in _walk(model):
        if isinstance(node, (KeywordCall, TemplateArguments)):
            yield node


def _walk(node):
    yield node
    for child in getattr(node, "body", []) or []:
        yield from _walk(child)
    for section in getattr(node, "sections", []) or []:
        yield from _walk(section)


def _variable_definitions(model: File) -> dict[str, tuple[str, int]]:
    """variable name (inner) -> (value, lineno) from *** Variables *** sections."""
    from robot.parsing.model.statements import Variable

    definitions = {}
    for node in _walk(model):
        if isinstance(node, Variable) and node.name:
            inner = node.name[2:-1] if node.name.startswith("${") else node.name
            values = node.value
            if values:
                definitions[inner] = (values[0], node.lineno)
    return definitions


def _imported_resources(model: File, base: Path) -> list[Path]:
    from robot.parsing.model.statements import ResourceImport

    paths = []
    for node in _walk(model):
        if isinstance(node, ResourceImport) and node.name:
            candidate = (base / node.name).resolve()
            if candidate.is_file():
                paths.append(candidate)
    return paths


def find_variable_usages(variable_name: str, root: Path) -> list[tuple[str, int]]:
    """All keyword-call usage sites of ${variable_name} under `root`."""
    marker = "${" + variable_name + "}"
    usages: list[tuple[str, int]] = []
    for path in sorted(root.rglob("*.robot")) + sorted(root.rglob("*.resource")):
        try:
            model = _parse(path)
        except Exception:
            continue
        for call in _iter_keyword_calls(model):
            for token in call.tokens:
                if token.type == "ARGUMENT" and marker in (token.value or ""):
                    usages.append((str(path), token.lineno))
                    break
    return usages


def resolve_fix(
    *,
    file: str,
    lineno: int | None,
    old_locator: str,
    new_locator: str,
    search_root: str | Path | None = None,
) -> ResolvedFix:
    """Resolve what must change for old->new at file:lineno."""
    path = Path(file)
    try:
        model = _parse(path)
    except Exception:
        return ResolvedFix(kind="unresolved", file=file, lineno=lineno)

    # find the argument token at (or nearest to) the failing line
    target_token = None
    for call in _iter_keyword_calls(model):
        for token in call.tokens:
            if token.type != "ARGUMENT":
                continue
            if lineno is not None and token.lineno != lineno:
                continue
            if token.value == old_locator or _resolves_to(token.value, old_locator, model, path):
                target_token = token
                break
        if target_token is not None:
            break
    if target_token is None:
        return ResolvedFix(kind="unresolved", file=file, lineno=lineno, old_token=old_locator)

    raw = target_token.value or ""
    if raw == old_locator:
        return ResolvedFix(
            kind="literal", file=file, lineno=target_token.lineno,
            old_token=raw, new_token=new_locator,
        )

    match = _VAR_PATTERN.match(raw)
    if not match:
        return ResolvedFix(kind="unresolved", file=file, lineno=target_token.lineno, old_token=raw)
    variable_name, suffix = match.group(1), match.group(2)

    definition = _find_definition(variable_name, model, path)
    if definition is None:
        return ResolvedFix(kind="unresolved", file=file, lineno=target_token.lineno, old_token=raw)
    def_file, def_value, _def_lineno = definition

    root = Path(search_root) if search_root else path.parent
    usages = find_variable_usages(variable_name, root)

    if suffix:
        if not old_locator.endswith(suffix):
            return ResolvedFix(kind="unresolved", file=file, lineno=target_token.lineno, old_token=raw)
        if new_locator.endswith(suffix):
            # variable part changed, suffix stayed
            new_value = new_locator[: -len(suffix)]
        else:
            new_value = new_locator  # conservative: move everything into the variable? no — fall back
            return ResolvedFix(
                kind="literal", file=file, lineno=target_token.lineno,
                old_token=raw, new_token=new_locator,
            )
        return ResolvedFix(
            kind="variable+suffix", file=file, lineno=target_token.lineno,
            old_token=raw, new_token=raw,
            variable_name=variable_name, variable_file=def_file,
            variable_old_value=def_value, variable_new_value=new_value,
            usages=usages,
        )

    return ResolvedFix(
        kind="variable", file=file, lineno=target_token.lineno,
        old_token=raw, new_token=raw,
        variable_name=variable_name, variable_file=def_file,
        variable_old_value=def_value, variable_new_value=new_locator,
        usages=usages,
    )


def _resolves_to(raw: str | None, locator: str, model: File, path: Path) -> bool:
    if not raw:
        return False
    match = _VAR_PATTERN.match(raw)
    if not match:
        return False
    definition = _find_definition(match.group(1), model, path)
    if definition is None:
        return False
    return definition[1] + match.group(2) == locator


def _find_definition(variable_name: str, model: File, path: Path) -> tuple[str, str, int] | None:
    """-> (file, value, lineno) searching the file itself then imported resources."""
    local = _variable_definitions(model)
    if variable_name in local:
        value, lineno = local[variable_name]
        return (str(path), value, lineno)
    for resource in _imported_resources(model, path.parent):
        try:
            resource_model = _parse(resource)
        except Exception:
            continue
        definitions = _variable_definitions(resource_model)
        if variable_name in definitions:
            value, lineno = definitions[variable_name]
            return (str(resource), value, lineno)
    return None
