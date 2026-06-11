"""DOM curation and selector generation (library-agnostic, bs4-based).

Ported from SelfHealing.utils with cleanups:
* `filter_by_fuzz_median` fixes the original score/item misalignment (it
  zipped per-key scores against items); items are now scored by their best
  matching attribute.
* No file-write side effects.
"""

from __future__ import annotations

import re
from statistics import mean

from bs4 import BeautifulSoup
from bs4.element import Tag
from thefuzz import fuzz

_KEEP_ATTRIBUTES = ("id", "class", "value", "name", "type", "placeholder", "role")
_STRIP_TAGS = ("script", "svg", "source", "animatetransform", "template", "head", "nav")


def _has_display_none(tag: Tag) -> bool:
    return "display: none" in tag.get("style", "")


def simplify_dom(source: str) -> str:
    """Reduce a page source to a compact, prompt-friendly DOM excerpt.

    Strips scripts/svg/nav/head/templates, hidden elements, and all
    attributes except the locator-relevant ones.
    """
    soup = BeautifulSoup(source, "html.parser")

    for tag_name in _STRIP_TAGS:
        for elem in soup.find_all(tag_name):
            elem.decompose()

    for element in soup.find_all(_has_display_none):
        element.decompose()
    for element in soup.find_all(attrs={"type": "hidden"}):
        element.decompose()

    for a_tag in soup.find_all("a"):
        del a_tag["href"]
        del a_tag["class"]
    for img_tag in soup.find_all("img"):
        del img_tag["class"]
        del img_tag["alt"]
        del img_tag["src"]

    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr not in _KEEP_ATTRIBUTES:
                del tag[attr]

    return str(soup.body if soup.body is not None else soup)


# ------------------------------------------------------------------ predicates


def is_leaf_or_lowest(element: Tag) -> bool:
    """True when the element has no children or is the lowest of its tag in the branch."""
    if not element.find():
        return True
    return not element.find_all(element.name)


def has_direct_text(tag: Tag) -> bool:
    return bool(tag.string and tag.string.strip() and not tag.find())


def has_parent_dialog_without_open(element: Tag) -> bool:
    try:
        return any(
            parent.name == "dialog" and not parent.has_attr("open")
            for parent in element.parents
        )
    except Exception:
        return True


def has_child_dialog_without_open(element: Tag) -> bool:
    try:
        return any(
            child.name == "dialog" and not child.has_attr("open")
            for child in element.children
            if isinstance(child, Tag)
        )
    except Exception:
        return True


def is_headline(tag: Tag) -> bool:
    return tag.name in ("h1", "h2", "h3", "h4", "h5", "h6")


def is_div_in_li(tag: Tag) -> bool:
    return tag.name == "div" and tag.find_parent("li") is not None


def is_p(tag: Tag) -> bool:
    return tag.name == "p"


#: never proposed as interaction targets (matches agents.locator.BLOCKED_TARGET_TAGS)
_BLOCKED_CANDIDATE_TAGS = frozenset({"iframe", "frame", "html", "body", "head"})


def is_proposal_candidate(element: Tag) -> bool:
    """Combined filter used when generating locator proposals from the DOM."""
    return (
        element.name not in _BLOCKED_CANDIDATE_TAGS
        and (is_leaf_or_lowest(element) or has_direct_text(element))
        and not has_parent_dialog_without_open(element)
        and not has_child_dialog_without_open(element)
        and not is_headline(element)
        and not is_div_in_li(element)
        and not is_p(element)
    )


# ------------------------------------------------------------------- selectors


def clean_text_for_selector(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def get_selector_count(soup: BeautifulSoup, selector: str) -> int:
    try:
        return len(soup.select(selector))
    except Exception:
        return 0


def is_selector_unique(soup: BeautifulSoup, selector: str) -> bool:
    return get_selector_count(soup, selector) == 1


def generate_unique_css_selector(  # noqa: C901 - faithful port of battle-tested heuristic
    element: Tag,
    soup: BeautifulSoup,
    check_parents: bool = True,
    check_siblings: bool = True,
    check_children: bool = True,
    check_text: bool = True,
    only_return_unique_selectors: bool = True,
    text_exclusions: list[str] | None = None,
) -> str | None:
    """Generate a short CSS selector uniquely matching `element` in `soup`."""
    text_exclusions = text_exclusions or []
    steps: list[str] = []
    text_steps: list[str] = []
    element_contains_text = False

    steps.append(f"{element.name}")

    for attr, fmt in (
        ("id", "#{}"),
        ("name", '[name="{}"]'),
        ("type", '[type="{}"]'),
        ("placeholder", '[placeholder="{}"]'),
        ("role", '[role="{}"]'),
    ):
        value = element.get(attr)
        if value:
            attr_selector = fmt.format(value)
            if is_selector_unique(soup, f"{element.name}{attr_selector}"):
                return f"{element.name}{attr_selector}"
            steps.append(attr_selector)

    if element.get("class"):
        class_list: list[str] = []
        class_selector = None
        for single_class in (x for x in element["class"] if "hidden" not in x):
            class_list.append(single_class)
            class_selector = "." + ".".join(class_list)
            if is_selector_unique(soup, f"{element.name}{class_selector}"):
                return f"{element.name}{class_selector}"
        if class_selector:
            steps.append(class_selector)

    if check_text and element.text.strip():
        element_contains_text = True
        selector_count = 0
        if element.string and element.string not in text_exclusions:
            sanitized = clean_text_for_selector(element.string)
            text_selector = f':-soup-contains-own("{sanitized}")'
            selector_count = get_selector_count(soup, f"{''.join(steps)}{text_selector}")
            if selector_count == 1:
                return f"{''.join(steps)}{text_selector}"
            if selector_count > 1:
                text_steps.append(text_selector)
        if not element.string or selector_count == 0:
            text_selectors: list[str] = []
            for text in element.stripped_strings:
                if text in text_exclusions:
                    continue
                sanitized = clean_text_for_selector(text)
                text_selector = f':-soup-contains("{sanitized}")'
                text_selectors.append(text_selector)
                selector_count = get_selector_count(soup, f"{''.join(steps)}{''.join(text_selectors)}")
                if selector_count == 1:
                    return f"{''.join(steps)}{''.join(text_selectors)}"
                if selector_count > 1:
                    text_steps.append(text_selector)
                elif selector_count == 0:
                    break

    li_parent = element.find_parent("li")
    ul_parent = element.find_parent("ul")
    if li_parent and ul_parent:
        ul_selector = generate_unique_css_selector(
            ul_parent, soup, check_parents=True, check_siblings=False,
            check_text=False, only_return_unique_selectors=False,
        )
        li_selector = generate_unique_css_selector(
            li_parent, soup, check_parents=False, check_siblings=False,
            check_text=False, only_return_unique_selectors=False,
        )
        candidate = f"{ul_selector} > {li_selector} {''.join(steps)}"
        if is_selector_unique(soup, candidate):
            return candidate
    elif ul_parent:
        ul_selector = generate_unique_css_selector(
            ul_parent, soup, check_parents=True, check_siblings=False,
            check_text=False, only_return_unique_selectors=False,
        )
        candidate = f"{ul_selector} > {''.join(steps)}"
        if is_selector_unique(soup, candidate):
            return candidate

    if check_siblings:
        exclusions = list(element.stripped_strings) if element_contains_text else None
        for sibling in element.find_previous_siblings():
            prev_selector = generate_unique_css_selector(
                sibling, soup, check_siblings=False, check_parents=False,
                check_children=False, only_return_unique_selectors=False,
                text_exclusions=exclusions,
            )
            if prev_selector:
                if is_selector_unique(soup, f"{prev_selector} + {''.join(steps)}"):
                    return f"{prev_selector} + {''.join(steps)}"
                if is_selector_unique(soup, f"{prev_selector} + {''.join(steps)}{''.join(text_steps)}"):
                    return f"{prev_selector} + {''.join(steps)}{''.join(text_steps)}"
        for sibling in element.find_next_siblings():
            next_selector = generate_unique_css_selector(
                sibling, soup, check_siblings=False, check_parents=False,
                check_children=False, only_return_unique_selectors=False,
            )
            if next_selector:
                candidate = f"{''.join(steps)}:has(+ {next_selector})"
                if is_selector_unique(soup, candidate):
                    return candidate

    if check_parents:
        max_level = 10
        parent_selectors: list[str] = []
        exclusions = list(element.stripped_strings) if element_contains_text else None
        for level, parent in enumerate(element.parents):
            if level >= max_level:
                break
            if parent is None or has_child_dialog_without_open(parent) or parent.name == "[document]":
                continue
            parent_selector = generate_unique_css_selector(
                parent, soup, check_children=False, check_siblings=True,
                check_parents=False, check_text=True,
                only_return_unique_selectors=False, text_exclusions=exclusions,
            )
            if parent_selector:
                parent_selectors.append(parent_selector)
                chained = f"{' > '.join(reversed(parent_selectors))} > {''.join(steps)}"
                direct = f"{parent_selector} {''.join(steps)}"
                if is_selector_unique(soup, direct):
                    return direct
                if is_selector_unique(soup, chained):
                    return chained

    if not only_return_unique_selectors:
        return "".join(steps)
    if is_selector_unique(soup, "".join(steps)):
        return "".join(steps)
    parent = element.find_parent()
    if parent is not None:
        same_tag_siblings = parent.find_all(element.name)
        if len(same_tag_siblings) > 1:
            # identity, not ==: equal-looking tags (same markup) are __eq__-equal
            index = next((i for i, e in enumerate(same_tag_siblings) if e is element), None)
            if index is not None:
                return f"{''.join(steps)}:nth-of-type({index + 1})"
    return None


def generate_proposals(source: str, tag_names: list[str | object]) -> list[str]:
    """Generate `css=` locator proposals for candidate elements of given types."""
    soup = BeautifulSoup(source, "html.parser")
    locators = []
    for elem in soup.find_all(tag_names):
        if not is_proposal_candidate(elem):
            continue
        selector = generate_unique_css_selector(elem, soup)
        if selector:
            locators.append("css=" + selector)
    return locators


# -------------------------------------------------------------- fuzzy filtering


def _best_score(item: dict, defined_value: str) -> int:
    scores = [
        fuzz.ratio(value, defined_value)
        for value in item.get("additional_info", {}).values()
        if isinstance(value, str)
    ]
    return max(scores, default=0)


def filter_by_fuzz(dict_list: list[dict], defined_value: str, threshold: int = 50) -> list[dict]:
    """Keep candidate items whose best attribute similarity exceeds `threshold`."""
    return [item for item in dict_list if _best_score(item, defined_value) > threshold]


def filter_by_fuzz_median(dict_list: list[dict], defined_value: str) -> list[dict]:
    """Keep candidate items scoring above the mean best-similarity of the list."""
    if not dict_list:
        return []
    scored = [(_best_score(item, defined_value), item) for item in dict_list]
    cutoff = mean(score for score, _ in scored)
    return [item for score, item in scored if score > cutoff]
