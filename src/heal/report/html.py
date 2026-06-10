"""Self-contained HTML dashboard rendered from the run store.

Healed AND unhealed transactions are first-class: the RCA for what could not
be healed is half the product. No external assets — one file, openable
anywhere, like RF's log.html.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from ..core.schemas import HealEvent
from .history import Hotspot
from .summary import build_summary

_TEMPLATE = Template(
    """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>heal report</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a2e; }
  h1 { font-size: 1.5rem; } h2 { font-size: 1.15rem; margin-top: 2rem; }
  .cards { display: flex; gap: 1rem; flex-wrap: wrap; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 0.8rem 1.4rem; min-width: 7rem; text-align: center; }
  .card .num { font-size: 1.8rem; font-weight: 700; }
  .healed .num { color: #0a7d33; } .unhealed .num { color: #c0392b; } .suppressed .num { color: #8a6d00; }
  table { border-collapse: collapse; width: 100%; margin-top: 0.6rem; }
  th, td { border: 1px solid #e2e2e2; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; font-size: 0.9rem; }
  th { background: #f5f6fa; }
  .badge { display: inline-block; border-radius: 10px; padding: 0.05rem 0.55rem; font-size: 0.78rem; color: #fff; }
  .b-healed { background: #0a7d33; } .b-unhealed { background: #c0392b; } .b-suppressed { background: #8a6d00; }
  details { margin: 0.2rem 0; } summary { cursor: pointer; }
  pre { background: #f7f7f9; border: 1px solid #eee; padding: 0.6rem; overflow-x: auto; font-size: 0.8rem; max-height: 24rem; }
  .meta { color: #666; font-size: 0.82rem; }
  .fix { background: #eef7ee; border-left: 4px solid #0a7d33; padding: 0.4rem 0.8rem; font-size: 0.88rem; }
  img.shot { max-width: 480px; border: 1px solid #ccc; }
</style>
</head>
<body>
<h1>heal report</h1>
<div class="cards">
  <div class="card"><div class="num">{{ summary.transactions }}</div>transactions</div>
  <div class="card healed"><div class="num">{{ summary.healed }}</div>healed</div>
  <div class="card unhealed"><div class="num">{{ summary.unhealed }}</div>unhealed</div>
  <div class="card suppressed"><div class="num">{{ summary.suppressed }}</div>suppressed</div>
  <div class="card"><div class="num">{{ summary.total_tokens }}</div>tokens</div>
</div>

<h2>Failure classes</h2>
<table><tr><th>class</th><th>count</th></tr>
{% for cls, n in summary.by_failure_class.items() %}<tr><td>{{ cls }}</td><td>{{ n }}</td></tr>{% endfor %}
</table>

{% if hotspots %}
<h2>Maintenance hotspots (healed repeatedly)</h2>
<table><tr><th>locator</th><th>file</th><th>heals</th><th>last</th></tr>
{% for h in hotspots %}<tr><td><code>{{ h.failed_locator }}</code></td><td>{{ h.source }}</td><td>{{ h.heal_count }}</td><td>{{ h.last_healed_at }}</td></tr>{% endfor %}
</table>
{% endif %}

<h2>Transactions</h2>
{% for e in events %}
<details {% if e.outcome and e.outcome.status.value != 'healed' %}open{% endif %}>
  <summary>
    <span class="badge b-{{ e.outcome.status.value if e.outcome else 'unhealed' }}">{{ e.outcome.status.value if e.outcome else '?' }}</span>
    <strong>{{ e.test_name }}</strong> — {{ e.keyword.name if e.keyword }}
    <span class="meta">{{ e.source }}{% if e.lineno %}:{{ e.lineno }}{% endif %}
      · {{ e.outcome.diagnosis.failure_class.value if e.outcome }} · {{ '%.1f'|format(e.outcome.duration_seconds if e.outcome else 0) }}s
      {% if e.outcome and e.outcome.usage.model %} · {{ e.outcome.usage.model }}/{{ e.outcome.usage.output_mode }}{% endif %}</span>
  </summary>
  {% if e.rca %}<p>{{ e.rca.clean_message }}</p>
    {% if e.rca.root_cause %}<p class="meta">root cause: {{ e.rca.root_cause }}</p>{% endif %}{% endif %}
  {% if e.outcome %}
    {% for a in e.outcome.attempts %}
      <p class="meta">attempt: {{ a.action.description }} — {{ 'ok' if a.succeeded else (a.detail or 'failed') }}</p>
    {% endfor %}
  {% endif %}
  {% if e.fix_proposal %}
    <div class="fix"><strong>fix proposal</strong> ({{ e.fix_proposal.blast_radius.value }}):
      <code>{{ e.fix_proposal.old_value }}</code> → <code>{{ e.fix_proposal.new_value }}</code>
      <span class="meta">{{ e.fix_proposal.file }}{% if e.fix_proposal.lineno %}:{{ e.fix_proposal.lineno }}{% endif %}</span>
    </div>
  {% endif %}
  {% if e.context %}
    {% set shot = e.context.evidence.get('screenshot') %}
    {% if shot and shot.path %}<p><img class="shot" src="{{ shot.path }}" alt="screenshot"/></p>{% endif %}
    {% set dom = e.context.evidence.get('dom-excerpt') %}
    {% if dom %}<details><summary class="meta">DOM excerpt</summary><pre>{{ dom.excerpt | e }}</pre></details>{% endif %}
    <details><summary class="meta">original error</summary><pre>{{ e.context.error_message | e }}</pre></details>
  {% endif %}
</details>
{% endfor %}
</body></html>
"""
)


def render_dashboard(
    events: list[HealEvent],
    path: str | Path,
    hotspots: list[Hotspot] | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = _TEMPLATE.render(events=events, summary=build_summary(events), hotspots=hotspots or [])
    path.write_text(html, encoding="utf-8")
    return path
