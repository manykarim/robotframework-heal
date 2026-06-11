"""Frame-evidence sizing probe (task 1.2): what does per-frame serialization
cost on a frame-heavy page, which filters make sense, do nested/cross-origin
frames behave?"""
import time
from pathlib import Path

import Browser

b = Browser.Browser()
b.new_browser(headless=True)
b.new_context()
b.new_page(f"file://{Path(__file__).parent}/pages/frame_heavy.html")
time.sleep(1)

from bs4 import BeautifulSoup

main = b.get_page_source()
soup = BeautifulSoup(main, "html.parser")
print(f"main DOM: {len(main)} chars")

for frame in soup.find_all(["iframe", "frame"]):
    fid = frame.get("id") or "?"
    selector = f"id={fid}"
    t0 = time.time()
    visible = False
    try:
        visible = "visible" in [str(s) for s in b.get_element_states(selector)]
    except Exception:
        pass
    try:
        bbox = b.get_boundingbox(selector)
        size = (bbox["width"], bbox["height"])
    except Exception:
        size = None
    try:
        html = b.evaluate_javascript(f"{selector} >>> css=html", "(el) => el.outerHTML")
        chars = len(html)
        ok = True
    except Exception as exc:
        chars, ok = 0, f"FAIL: {type(exc).__name__}: {str(exc)[:60]}"
    print(f"frame {fid:14} visible={visible} size={size} serialize={ok if ok is not True else 'ok'} "
          f"chars={chars} t={time.time()-t0:.2f}s")

# nested: can we reach the inner frame through two levels of piercing?
try:
    inner = b.evaluate_javascript("id=nested-outer >>> id=nested-inner >>> css=html", "(el) => el.outerHTML")
    print(f"two-level pierce: ok, {len(inner)} chars, contains frame-submit={'frame-submit' in inner}")
except Exception as exc:
    print(f"two-level pierce: FAIL {type(exc).__name__}: {str(exc)[:80]}")

# count through two levels?
try:
    print("two-level count:", b.get_element_count("id=nested-outer >>> id=nested-inner >>> id=frame-submit"))
except Exception as exc:
    print(f"two-level count: FAIL {str(exc)[:80]}")

b.close_browser("ALL")
