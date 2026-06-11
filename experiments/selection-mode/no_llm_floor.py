"""How many recorded heals could a ZERO-LLM path have solved?

Pipeline: deterministic candidates (generate_proposals, keyword-filtered)
-> score each candidate's text/attrs against the failed locator's tokens
(thefuzz) -> if the top candidate is unambiguous (margin), pick it.
Ground truth: the verified healed locator recorded in the run stores.
"""
import glob
import os
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from thefuzz import fuzz

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
os.chdir(Path(__file__).parents[2])

from heal.core.schemas import EvidenceKind  # noqa: E402
from heal.drivers.dom import generate_proposals  # noqa: E402
from heal.report.store import load_events  # noqa: E402

KEYWORD_TAGS = {
    "click": ["button", "a", "input", "label", "li"],
    "fill": ["input", "textarea"],
    "type": ["input", "textarea"],
    "select options": ["select"],
}


def tags_for(keyword):
    kw = keyword.lower()
    for marker, tags in KEYWORD_TAGS.items():
        if marker in kw:
            return tags
    return ["button", "a", "input", "select", "label", "li", "span"]


def normalize(locator):
    out = locator
    for p in ("css=", "id=", "xpath="):
        out = out.removeprefix(p)
    return out.replace("_", " ").replace("-", " ").replace("#", " ").replace(".", " ").strip()


def score(el, needle):
    hay = " ".join(
        [el.get_text(strip=True)[:80]]
        + [str(v) for k, v in el.attrs.items() if k in ("id", "name", "placeholder", "class", "type")]
    )
    return max(
        fuzz.token_set_ratio(needle, hay),
        fuzz.partial_ratio(needle.lower(), hay.lower()),
    )


def main():
    cases = solved = ambiguous = wrong = missed = 0
    times = []
    seen = set()
    for path in glob.glob("results/*/heal/events.jsonl"):
        for e in load_events(path):
            if not (e.outcome and e.outcome.healed_locator and e.context):
                continue
            dom = e.context.evidence_of(EvidenceKind.DOM_EXCERPT)
            if not dom or not dom.excerpt:
                continue
            key = (e.context.failed_locator, e.outcome.healed_locator)
            if key in seen:
                continue
            seen.add(key)
            css = e.outcome.healed_locator
            for p in ("css=", "id="):
                if css.startswith(p):
                    css = ("#" + css[3:]) if p == "id=" else css[4:]
                    break
            else:
                continue
            css = css.replace(":visible", "").replace(" >> nth=0", "")
            soup = BeautifulSoup(dom.excerpt, "html.parser")
            try:
                matches = soup.select(css)
            except Exception:
                continue
            if len(matches) != 1:
                continue
            truth = matches[0]
            cases += 1

            t0 = time.time()
            candidates = generate_proposals(dom.excerpt, tags_for(e.keyword.name))
            needle = normalize(e.context.failed_locator)
            scored = []
            for cand in candidates:
                try:
                    el = soup.select(cand.removeprefix("css="))[0]
                except Exception:
                    continue
                scored.append((score(el, needle), cand, el))
            scored.sort(key=lambda x: -x[0])
            times.append(time.time() - t0)

            if not scored:
                missed += 1
                continue
            top = scored[0]
            margin = top[0] - (scored[1][0] if len(scored) > 1 else 0)
            confident = top[0] >= 75 and margin >= 15
            if confident and top[2] is truth:
                solved += 1
            elif confident:
                wrong += 1
                print(f"  WRONG: {e.suite_name.split('.')[-1]} {e.context.failed_locator!r} -> {top[1]} (truth {e.outcome.healed_locator})")
            else:
                ambiguous += 1
    print(f"\ncases={cases}  zero-LLM-solved={solved} ({100*solved/cases:.0f}%)  "
          f"wrong-confident={wrong}  ambiguous->LLM={ambiguous}  no-candidates={missed}")
    print(f"candidate+scoring time: median={sorted(times)[len(times)//2]*1000:.0f}ms  max={max(times)*1000:.0f}ms")


if __name__ == "__main__":
    main()
