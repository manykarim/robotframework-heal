import cProfile, pstats, io
from pstats import SortKey
import pytest
from SelfHealing import browser_healing, utils
from SelfHealing.browser_healing import is_leaf_or_lowest, has_parent_dialog_without_open, has_child_dialog_without_open
from bs4 import BeautifulSoup
from pathlib import Path

testdata_dir = Path(__file__).parent.resolve() / "testdata"

def get_selectors():
    f = open(f"{testdata_dir}/todo_page_with_2_items.html", "r")
    full_source = f.read()
    full_soup = BeautifulSoup(full_source, 'html.parser')
    source = browser_healing.get_simplified_dom_tree(str(full_soup.body))
    soup = BeautifulSoup(source, 'html.parser')
    # element_types = ['a']
    element_types = ['a', 'button', 'checkbox', 'link', 'input', 'label', 'li']
    elements = soup.body.find_all(element_types)
    filtered_elements = [elem for elem in elements if (is_leaf_or_lowest(elem) and (not has_parent_dialog_without_open(elem)) and (not has_child_dialog_without_open(elem)))]

    selectors = []
    f = open("selectors.csv", "w")
    for elem in filtered_elements:
        f.write(f"{str(elem).replace("\n","")};")
        print(f"Element: {elem}")
        selector = browser_healing.generate_unique_css_selector(elem, soup)
        f.write(f"{selector}\n")
        print(f"Selector: {selector}")
        selectors.append(selector)
    return selectors


def main():
    print("Start Profiling")

    pr = cProfile.Profile()
    pr.enable()
    selectors = get_selectors()
    pr.disable()
    s = io.StringIO()
    sortby = SortKey.CUMULATIVE
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()
    print(s.getvalue())

if __name__ == "__main__":
    main()