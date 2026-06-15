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

#: single-variable argument shape: optional literal prefix, ${NAME}, optional suffix
_ARG_PATTERN = re.compile(r"^(?P<prefix>[^$]*)\$\{(?P<name>[^}]+)\}(?P<suffix>[^$]*)$", re.DOTALL)


@dataclass
class ResolvedFix:
    """What has to change to make a healed locator permanent."""

    kind: str  # "literal" | "variable" | "variable+suffix" | "keyword-argument" | "unresolved"
    file: str  # file containing the token to change (call site for literal)
    lineno: int | None
    old_token: str = ""
    new_token: str = ""
    variable_name: str = ""  # for variable kinds / the keyword-argument name
    variable_file: str = ""  # where the variable is defined
    variable_old_value: str = ""
    variable_new_value: str = ""
    usages: list[tuple[str, int]] = field(default_factory=list)  # (file, lineno)
    #: keyword-argument flow: (file, lineno, old_token, new_token) call-site edits
    call_site_edits: list[tuple[str, int, str, str]] = field(default_factory=list)

    @property
    def blast_radius(self) -> str:
        if self.kind == "literal":
            return "local"
        if self.kind == "keyword-argument":
            return "shared" if len(self.call_site_edits) > 1 else "local"
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


def default_search_root(file: str | Path) -> Path:
    """Repo root when available, else the file's directory — call sites and
    variable usages routinely live outside the failing file's folder."""
    import subprocess

    parent = Path(file).parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(parent), capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except Exception:
        pass
    return parent


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

    # find the argument token at (or nearest to) the failing line; a bare
    # ${var} at the exact line is kept as fallback (keyword-argument flow,
    # where the value only exists at call sites)
    target_token = None
    fallback_token = None
    for call in _iter_keyword_calls(model):
        for token in call.tokens:
            if token.type != "ARGUMENT":
                continue
            if lineno is not None and token.lineno != lineno:
                continue
            if token.value == old_locator or _resolves_to(token.value, old_locator, model, path):
                target_token = token
                break
            if fallback_token is None and lineno is not None and _ARG_PATTERN.match(token.value or ""):
                fallback_token = token
        if target_token is not None:
            break
    if target_token is None:
        target_token = fallback_token
    if target_token is None:
        return ResolvedFix(kind="unresolved", file=file, lineno=lineno, old_token=old_locator)

    raw = target_token.value or ""
    if raw == old_locator:
        return ResolvedFix(
            kind="literal", file=file, lineno=target_token.lineno,
            old_token=raw, new_token=new_locator,
        )

    match = _ARG_PATTERN.match(raw)
    if not match:
        return ResolvedFix(kind="unresolved", file=file, lineno=target_token.lineno, old_token=raw)
    prefix, variable_name, suffix = match.group("prefix"), match.group("name"), match.group("suffix")

    definition = _find_definition(variable_name, model, path)
    if definition is None:
        # not a Variables-section variable: maybe a user-keyword argument
        traced = _trace_keyword_argument(
            model, path, target_token, variable_name, old_locator, new_locator,
            Path(search_root) if search_root else default_search_root(path),
        )
        if traced is not None:
            return traced
        return ResolvedFix(kind="unresolved", file=file, lineno=target_token.lineno, old_token=raw)
    def_file, def_value, _def_lineno = definition

    root = Path(search_root) if search_root else default_search_root(path)
    usages = find_variable_usages(variable_name, root)

    # the variable's value portion is what sits between prefix and suffix
    if not (old_locator.startswith(prefix) and old_locator.endswith(suffix)
            and len(old_locator) >= len(prefix) + len(suffix)):
        return ResolvedFix(kind="unresolved", file=file, lineno=target_token.lineno, old_token=raw)
    if new_locator.startswith(prefix) and new_locator.endswith(suffix) and len(new_locator) >= len(prefix) + len(suffix):
        new_value = new_locator[len(prefix): len(new_locator) - len(suffix)]
        return ResolvedFix(
            kind="variable" if not (prefix or suffix) else "variable+suffix",
            file=file, lineno=target_token.lineno,
            old_token=raw, new_token=raw,
            variable_name=variable_name, variable_file=def_file,
            variable_old_value=def_value, variable_new_value=new_value,
            usages=usages,
        )
    # literal prefix/suffix changed too -> conservative call-site replacement
    return ResolvedFix(
        kind="literal", file=file, lineno=target_token.lineno,
        old_token=raw, new_token=new_locator,
    )


def _resolves_to(raw: str | None, locator: str, model: File, path: Path) -> bool:
    if not raw:
        return False
    match = _ARG_PATTERN.match(raw)
    if not match:
        return False
    definition = _find_definition(match.group("name"), model, path)
    if definition is None:
        return False
    return match.group("prefix") + definition[1] + match.group("suffix") == locator


# ------------------------------------------------- keyword-argument tracing


def _normalize_keyword_name(name: str) -> str:
    return name.lower().replace(" ", "").replace("_", "").split(".")[-1]


def _enclosing_keyword(model: File, lineno: int):
    """The user-keyword block containing `lineno`, or None (test bodies etc.)."""
    from robot.parsing.model.blocks import Keyword, KeywordSection

    for section in getattr(model, "sections", []) or []:
        if not isinstance(section, KeywordSection):
            continue
        for keyword in section.body:
            if isinstance(keyword, Keyword) and keyword.lineno <= lineno <= (keyword.end_lineno or keyword.lineno):
                return keyword
    return None


def _keyword_arguments(keyword) -> list[tuple[str, str | None, object]]:
    """[(name, default_or_None, arguments_statement)] from [Arguments]."""
    from robot.parsing.model.statements import Arguments

    for statement in keyword.body:
        if isinstance(statement, Arguments):
            out = []
            for value in statement.values:
                name, _, default = value.partition("=")
                inner = name[2:-1] if name.startswith("${") else name
                out.append((inner, default if "=" in value else None, statement))
            return out
    return []


def _trace_keyword_argument(
    model: File,
    path: Path,
    target_token,
    arg_name: str,
    old_locator: str,
    new_locator: str,
    root: Path,
) -> ResolvedFix | None:
    """One-hop flow (design D4): the failing argument is a user-keyword
    argument — fix the call sites that pass the broken value (or the variable
    they pass), never the keyword body."""
    keyword = _enclosing_keyword(model, target_token.lineno)
    if keyword is None or "${" in (keyword.name or ""):  # embedded-args keywords excluded
        return None
    arguments = _keyword_arguments(keyword)
    arg_names = [name for name, _, _ in arguments]
    if arg_name not in arg_names:
        return None
    position = arg_names.index(arg_name)
    default = arguments[position][1]
    wanted_name = _normalize_keyword_name(keyword.name)

    edits: list[tuple[str, int, str, str]] = []
    variable_target: tuple[str, str] | None = None  # (file-of-call, ${VAR} name)
    for candidate in sorted(root.rglob("*.robot")) + sorted(root.rglob("*.resource")):
        try:
            candidate_model = _parse(candidate)
        except Exception:
            continue
        for call in _iter_keyword_calls(candidate_model):
            name_token = next((t for t in call.tokens if t.type == "KEYWORD"), None)
            if name_token is None or _normalize_keyword_name(name_token.value or "") != wanted_name:
                continue
            arg_tokens = [t for t in call.tokens if t.type == "ARGUMENT"]
            positional: list = []
            named: dict[str, object] = {}
            for token in arg_tokens:
                head, sep, _tail = (token.value or "").partition("=")
                if sep and head in arg_names:
                    named[head] = token
                else:
                    positional.append(token)
            token = named.get(arg_name) or (positional[position] if position < len(positional) else None)
            if token is None:
                continue
            value = (token.value or "")
            if token is named.get(arg_name):
                value = value.partition("=")[2]
            if value == old_locator:
                old_tok = token.value or ""
                new_tok = f"{arg_name}={new_locator}" if token is named.get(arg_name) else new_locator
                edits.append((str(candidate), token.lineno, old_tok, new_tok))
            else:
                var_match = _ARG_PATTERN.match(value)
                if var_match and not var_match.group("prefix") and not var_match.group("suffix"):
                    definition = _find_definition(var_match.group("name"), candidate_model, candidate)
                    if definition and definition[1] == old_locator:
                        variable_target = (var_match.group("name"), definition[0])

    if variable_target is not None and not edits:
        var_name, def_file = variable_target
        return ResolvedFix(
            kind="variable", file=str(path), lineno=target_token.lineno,
            variable_name=var_name, variable_file=def_file,
            variable_old_value=old_locator, variable_new_value=new_locator,
            usages=find_variable_usages(var_name, root),
        )
    if not edits and default == old_locator:
        # nobody overrides the argument: fix the default in [Arguments]
        statement = arguments[position][2]
        edits.append(
            (str(path), statement.lineno, f"${{{arg_name}}}={old_locator}", f"${{{arg_name}}}={new_locator}")
        )
    if not edits:
        return None
    return ResolvedFix(
        kind="keyword-argument", file=str(path), lineno=target_token.lineno,
        variable_name=arg_name,
        call_site_edits=edits,
        usages=[(f, line) for f, line, _, _ in edits],
    )


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
