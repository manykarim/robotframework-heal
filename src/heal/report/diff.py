"""Side-by-side HTML diff renderer for healed files (design D2).

Built on difflib.SequenceMatcher opcodes: line-level pairing with a second
token-level pass inside modified line pairs for word highlighting. Output is
fully self-contained (inline CSS, no scripts/fonts) so CI artifact downloads
render offline. Unchanged context folds into expandable <details> blocks.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

CONTEXT_LINES = 3
_TOKEN = re.compile(r"\s+|\w+|[^\w\s]")

DIFF_CSS = """
body { font-family: system-ui, sans-serif; margin: 1.5rem; color: #1a1a2e; }
h1 { font-size: 1.25rem; } a { color: #2b5fad; }
.summary { border: 1px solid #ddd; border-radius: 8px; padding: 0.7rem 1rem; margin-bottom: 1rem; }
.summary .meta { color: #666; font-size: 0.85rem; }
.mapping { font-family: ui-monospace, monospace; font-size: 0.85rem; margin: 0.25rem 0; }
.badge { display: inline-block; border-radius: 10px; padding: 0 0.5rem; font-size: 0.72rem; color: #fff; vertical-align: middle; }
.b-local { background: #0a7d33; } .b-shared { background: #b35c00; }
table.diff { border-collapse: collapse; width: 100%; font-family: ui-monospace, monospace; font-size: 0.8rem; table-layout: fixed; }
table.diff td { border: 0; padding: 0.1rem 0.5rem; vertical-align: top; white-space: pre-wrap; word-break: break-all; }
td.num { width: 3.2rem; text-align: right; color: #999; background: #f7f7f9; user-select: none; border-right: 1px solid #e8e8ee; }
td.line { width: 50%; }
tr.del td.line.left { background: #ffecec; } tr.del td.num.left { background: #ffdce0; }
tr.ins td.line.right { background: #eaffea; } tr.ins td.num.right { background: #cdf2cd; }
tr.chg td.line.left { background: #fff5f5; } tr.chg td.line.right { background: #f2fff2; }
span.hl-del { background: #ffb6ba; border-radius: 2px; }
span.hl-ins { background: #97e8a9; border-radius: 2px; }
details.fold { margin: 0; } details.fold summary { cursor: pointer; color: #888; background: #fafafc;
  font-size: 0.75rem; padding: 0.15rem 0.6rem; border-top: 1px dashed #e0e0e8; border-bottom: 1px dashed #e0e0e8; }
.filehead { background: #f5f6fa; border: 1px solid #e2e2e8; border-bottom: 0; padding: 0.4rem 0.8rem;
  font-family: ui-monospace, monospace; font-size: 0.85rem; border-radius: 8px 8px 0 0; }
.diffwrap { border: 1px solid #e2e2e8; border-radius: 0 0 8px 8px; overflow: hidden; margin-bottom: 1.5rem; }
"""


@dataclass
class FixMapping:
    """Per-file summary line for the diff header."""

    old_value: str
    new_value: str
    blast_radius: str = "local"


@dataclass
class DiffStats:
    changed: int = 0
    added: int = 0
    removed: int = 0

    @property
    def total(self) -> int:
        return self.changed + self.added + self.removed


@dataclass
class _Row:
    kind: str  # equal | chg | del | ins
    left_no: int | None = None
    left: str = ""
    right_no: int | None = None
    right: str = ""
    left_html: str | None = None
    right_html: str | None = None


def _tokenize(line: str) -> list[str]:
    return _TOKEN.findall(line)


def _coalesce(opcodes: list, old_tokens: list[str], gap_chars: int = 2) -> list:
    """Absorb tiny equal runs BETWEEN two changes so highlights read as one
    unit (e.g. 'id=login-button' -> one span, not three split on '=' / '-')."""
    merged: list = []
    for index, op in enumerate(opcodes):
        is_tiny_gap = (
            op[0] == "equal"
            and merged
            and merged[-1][0] != "equal"
            and index + 1 < len(opcodes)
            and opcodes[index + 1][0] != "equal"
            and len("".join(old_tokens[op[1]:op[2]])) <= gap_chars
        )
        merged.append(("replace", op[1], op[2], op[3], op[4]) if is_tiny_gap else op)
    # join adjacent non-equal opcodes into single spans
    joined: list = []
    for op in merged:
        if joined and joined[-1][0] != "equal" and op[0] != "equal":
            prev = joined.pop()
            joined.append(("replace", prev[1], op[2], prev[3], op[4]))
        else:
            joined.append(op)
    return joined


def _intraline(old: str, new: str) -> tuple[str, str]:
    """HTML for a modified line pair with changed tokens highlighted."""
    old_tokens, new_tokens = _tokenize(old), _tokenize(new)
    left_parts: list[str] = []
    right_parts: list[str] = []
    opcodes = _coalesce(
        list(SequenceMatcher(None, old_tokens, new_tokens, autojunk=False).get_opcodes()),
        old_tokens,
    )
    for op, a1, a2, b1, b2 in opcodes:
        old_chunk = html.escape("".join(old_tokens[a1:a2]))
        new_chunk = html.escape("".join(new_tokens[b1:b2]))
        if op == "equal":
            left_parts.append(old_chunk)
            right_parts.append(new_chunk)
        else:
            if old_chunk:
                left_parts.append(f'<span class="hl-del">{old_chunk}</span>')
            if new_chunk:
                right_parts.append(f'<span class="hl-ins">{new_chunk}</span>')
    return "".join(left_parts), "".join(right_parts)


def diff_rows(original: str, healed: str) -> tuple[list[_Row], DiffStats]:
    old_lines = original.splitlines()
    new_lines = healed.splitlines()
    rows: list[_Row] = []
    stats = DiffStats()
    for op, a1, a2, b1, b2 in SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
        if op == "equal":
            for offset in range(a2 - a1):
                rows.append(_Row("equal", a1 + offset + 1, old_lines[a1 + offset], b1 + offset + 1, new_lines[b1 + offset]))
        elif op == "replace":
            pairs = max(a2 - a1, b2 - b1)
            for offset in range(pairs):
                left_idx = a1 + offset if a1 + offset < a2 else None
                right_idx = b1 + offset if b1 + offset < b2 else None
                if left_idx is not None and right_idx is not None:
                    left_html, right_html = _intraline(old_lines[left_idx], new_lines[right_idx])
                    rows.append(_Row("chg", left_idx + 1, old_lines[left_idx], right_idx + 1, new_lines[right_idx],
                                     left_html=left_html, right_html=right_html))
                    stats.changed += 1
                elif left_idx is not None:
                    rows.append(_Row("del", left_idx + 1, old_lines[left_idx]))
                    stats.removed += 1
                else:
                    rows.append(_Row("ins", None, "", right_idx + 1, new_lines[right_idx]))
                    stats.added += 1
        elif op == "delete":
            for idx in range(a1, a2):
                rows.append(_Row("del", idx + 1, old_lines[idx]))
                stats.removed += 1
        elif op == "insert":
            for idx in range(b1, b2):
                rows.append(_Row("ins", None, "", idx + 1, new_lines[idx]))
                stats.added += 1
    return rows, stats


def _cell(row: _Row) -> str:
    left = row.left_html if row.left_html is not None else html.escape(row.left)
    right = row.right_html if row.right_html is not None else html.escape(row.right)
    left_no = row.left_no if row.left_no is not None else ""
    right_no = row.right_no if row.right_no is not None else ""
    return (
        f'<tr class="{row.kind}"><td class="num left">{left_no}</td><td class="line left">{left}</td>'
        f'<td class="num right">{right_no}</td><td class="line right">{right}</td></tr>'
    )


def _render_rows(rows: list[_Row]) -> str:
    """Rows with long equal runs folded into <details>."""
    out: list[str] = []
    buffer: list[_Row] = []

    def flush(next_is_change: bool, first_block: bool):
        if not buffer:
            return
        keep_tail = 0 if not next_is_change else CONTEXT_LINES
        keep_head = 0 if first_block else CONTEXT_LINES
        if len(buffer) <= keep_head + keep_tail + 2:
            out.extend(_cell(r) for r in buffer)
        else:
            out.extend(_cell(r) for r in buffer[:keep_head])
            folded = buffer[keep_head: len(buffer) - keep_tail if keep_tail else len(buffer)]
            out.append(
                '<tr><td colspan="4" style="padding:0"><details class="fold">'
                f"<summary>… {len(folded)} unchanged line(s)</summary><table class='diff'>"
                + "".join(_cell(r) for r in folded)
                + "</table></details></td></tr>"
            )
            if keep_tail:
                out.extend(_cell(r) for r in buffer[-keep_tail:])
        buffer.clear()

    first = True
    for index, row in enumerate(rows):
        if row.kind == "equal":
            buffer.append(row)
        else:
            flush(next_is_change=True, first_block=first)
            first = False
            out.append(_cell(row))
    flush(next_is_change=False, first_block=first)
    return "".join(out)


def render_file_diff(
    original: str,
    healed: str,
    *,
    file_label: str,
    mappings: list[FixMapping] | None = None,
) -> tuple[str, DiffStats]:
    rows, stats = diff_rows(original, healed)
    mapping_html = "".join(
        f'<div class="mapping"><span class="badge b-{m.blast_radius}">{m.blast_radius}</span> '
        f'<span class="hl-del">{html.escape(m.old_value)}</span> → '
        f'<span class="hl-ins">{html.escape(m.new_value)}</span></div>'
        for m in (mappings or [])
    )
    page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>heal diff: {html.escape(file_label)}</title>
<style>{DIFF_CSS}</style></head>
<body>
<h1>heal diff — {html.escape(file_label)}</h1>
<div class="summary">
  {mapping_html}
  <div class="meta">{stats.changed} modified · {stats.added} added · {stats.removed} removed line(s)
   — healed copy only, the original file is untouched</div>
</div>
<div class="filehead">{html.escape(file_label)}</div>
<div class="diffwrap"><table class="diff">{_render_rows(rows)}</table></div>
</body></html>"""
    return page, stats


@dataclass
class DiffPage:
    source: str
    path: Path
    stats: DiffStats = field(default_factory=DiffStats)


def write_diff_pages(
    changes: list,  # list[FileChange] from heal.fix.apply
    out_dir: str | Path,
    mappings_by_file: dict[str, list[FixMapping]] | None = None,
) -> list[DiffPage]:
    """One diff page per changed file plus an index. Returns the pages."""
    out_dir = Path(out_dir)
    pages: list[DiffPage] = []
    for change in changes:
        if not change.changed:
            continue
        source = Path(change.path)
        page_html, stats = render_file_diff(
            change.original,
            change.healed,
            file_label=str(source),
            mappings=(mappings_by_file or {}).get(change.path, []),
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        page_path = out_dir / f"{source.stem}.diff.html"
        page_path.write_text(page_html, encoding="utf-8")
        pages.append(DiffPage(source=change.path, path=page_path, stats=stats))
    if pages:
        index_rows = "".join(
            f'<li><a href="{p.path.name}">{html.escape(p.source)}</a>'
            f' <span class="meta">({p.stats.total} change(s))</span></li>'
            for p in pages
        )
        (out_dir / "index.html").write_text(
            f"<!DOCTYPE html><html><head><meta charset='utf-8'/><title>heal diffs</title>"
            f"<style>{DIFF_CSS}</style></head><body><h1>Healed file diffs</h1>"
            f"<ul>{index_rows}</ul></body></html>",
            encoding="utf-8",
        )
    return pages
