from bs4 import BeautifulSoup

from heal.drivers.dom import (
    filter_by_fuzz,
    filter_by_fuzz_median,
    generate_proposals,
    generate_unique_css_selector,
    has_direct_text,
    is_leaf_or_lowest,
    is_proposal_candidate,
    simplify_dom,
)

PAGE = """<html>
<head><title>x</title><script>var a=1;</script></head>
<body>
  <nav><a href="/home" class="navlink">Home</a></nav>
  <script>var b=2;</script>
  <div style="display: none">secret</div>
  <input type="hidden" name="csrf" value="tok"/>
  <form id="login-form" data-test="login" aria-label="Login">
    <label for="user-email">Email</label>
    <input id="user-email" name="email" type="text" onclick="track()"/>
    <button id="signin-btn" type="submit">Sign in</button>
  </form>
  <ul id="menu"><li><span>Alpha</span></li><li><span>Beta</span></li></ul>
</body></html>"""


def test_simplify_dom_strips_noise_and_keeps_locator_attributes():
    out = simplify_dom(PAGE)
    assert "<script" not in out and "<nav" not in out
    assert "display: none" not in out and "secret" not in out
    assert 'type="hidden"' not in out
    assert "onclick" not in out and "data-test" not in out and "aria-label" not in out
    assert 'id="user-email"' in out and 'name="email"' in out
    assert "Sign in" in out


def test_simplify_dom_without_body():
    assert "stub" in simplify_dom("<div>stub</div>")


def test_unique_selector_prefers_id():
    soup = BeautifulSoup(PAGE, "html.parser")
    button = soup.find("button")
    assert generate_unique_css_selector(button, soup) == "button#signin-btn"


def test_unique_selector_text_and_structure_fallback():
    html = """<body>
      <div><button class="btn">Save</button></div>
      <div><button class="btn">Cancel</button></div>
    </body>"""
    soup = BeautifulSoup(html, "html.parser")
    save = soup.find_all("button")[0]
    selector = generate_unique_css_selector(save, soup)
    assert selector is not None
    assert len(soup.select(selector)) == 1
    assert soup.select(selector)[0] is save


def test_unique_selector_sibling_disambiguation():
    html = "<body><p>one</p><p>one</p></body>"
    soup = BeautifulSoup(html, "html.parser")
    second = soup.find_all("p")[1]
    selector = generate_unique_css_selector(second, soup, check_text=False)
    assert selector is not None
    assert [e is second for e in soup.select(selector)] == [True]


def test_unique_selector_nth_of_type_fallback():
    html = "<body><p>one</p><p>one</p></body>"
    soup = BeautifulSoup(html, "html.parser")
    second = soup.find_all("p")[1]
    selector = generate_unique_css_selector(second, soup, check_text=False, check_siblings=False)
    assert selector == "p:nth-of-type(2)"
    assert soup.select(selector)[0] is second


def test_predicates():
    soup = BeautifulSoup(PAGE, "html.parser")
    button = soup.find("button")
    assert is_leaf_or_lowest(button)
    assert has_direct_text(button)
    assert is_proposal_candidate(button)
    # div inside li and headlines are excluded from proposals
    li_soup = BeautifulSoup("<body><li><div>x</div></li><h1>t</h1></body>", "html.parser")
    assert not is_proposal_candidate(li_soup.find("div"))
    assert not is_proposal_candidate(li_soup.find("h1"))


def test_generate_proposals_unique_and_prefixed():
    proposals = generate_proposals(simplify_dom(PAGE), ["button", "input"])
    assert any("signin-btn" in p for p in proposals)
    assert all(p.startswith("css=") for p in proposals)
    soup = BeautifulSoup(simplify_dom(PAGE), "html.parser")
    for p in proposals:
        assert len(soup.select(p.removeprefix("css="))) == 1


CANDIDATES = [
    {"locator": "a", "additional_info": {"innerText": "Sign in", "id": "signin-btn"}},
    {"locator": "b", "additional_info": {"innerText": "totally unrelated paragraph text"}},
    {"locator": "c", "additional_info": {"innerText": "Sign in now"}},
]


def test_filter_by_fuzz_threshold():
    kept = filter_by_fuzz(CANDIDATES, "Sign in", threshold=50)
    assert {c["locator"] for c in kept} == {"a", "c"}


def test_filter_by_fuzz_median_keeps_best_aligned_items():
    kept = filter_by_fuzz_median(CANDIDATES, "Sign in")
    locators = {c["locator"] for c in kept}
    assert "a" in locators and "b" not in locators


def test_filter_by_fuzz_median_empty():
    assert filter_by_fuzz_median([], "x") == []


def test_describe_and_rank_candidates():
    from heal.drivers.dom import candidate_tags_for, describe_candidates, rank_candidates

    html = """<body>
      <input id="user-email" name="email" placeholder="you@example.com"/>
      <input id="search-box" name="q"/>
      <button id="signin-btn">Sign in</button></body>"""
    candidates = ["css=#user-email", "css=#search-box", "css=#signin-btn"]
    infos = describe_candidates(html, candidates)
    assert [i["locator"] for i in infos] == candidates
    assert infos[0]["attrs"]["placeholder"] == "you@example.com"

    ranked = rank_candidates(infos, "id=email_field")
    assert ranked[0]["locator"] == "css=#user-email"
    assert ranked[0]["score"] >= ranked[-1]["score"]

    assert candidate_tags_for("Fill Text") == ["input", "textarea"]
    assert "button" in candidate_tags_for("Click")
    assert "select" in candidate_tags_for("Select Options By")
