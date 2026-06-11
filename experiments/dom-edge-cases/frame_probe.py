"""Can the BrowserDriver primitives support frame-aware healing?

Q1: does get_element_count pierce frames with `frame >>> inner`?
Q2: can we serialize a frame's DOM via evaluate_javascript on `frame >>> html`?
Q3: can we enumerate iframes from the main-frame DOM?
"""
from pathlib import Path

import Browser

b = Browser.Browser()
b.new_browser(headless=True)
b.new_context()
b.new_page(f"file://{Path(__file__).parent}/pages/frames.html")

print("Q1 count main-frame button:", b.get_element_count("id=frame-submit"))
print("Q1 count pierced button:", b.get_element_count("id=content-frame >>> id=frame-submit"))
print("Q1 count pierced css:", b.get_element_count("css=#content-frame >>> css=button#frame-submit"))

html = b.evaluate_javascript("id=content-frame >>> css=html", "(el) => el.outerHTML")
print("Q2 frame html length:", len(html), "| contains frame-submit:", "frame-submit" in html)

from bs4 import BeautifulSoup
soup = BeautifulSoup(b.get_page_source(), "html.parser")
frames = [(f.get("id"), f.get("src")) for f in soup.find_all(["iframe", "frame"])]
print("Q3 frames found in main DOM:", frames)

states = b.get_element_states("id=content-frame >>> id=frame-submit")
print("Q1b states via pierce:", [str(s) for s in states][:4])
b.close_browser("ALL")
