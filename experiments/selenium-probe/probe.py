"""Selenium primitive probe (task 4.1): which SessionDriver primitives can a
SeleniumLibrary instance provide, and how?

Checks: count/visibility via find_elements, readyState/innerText/viewport/
scroll via execute_script, page source, screenshot bytes, fill via
clear+send_keys, locator prefix acceptance in SL keywords, dialog detection
from page source, shadow-DOM serialization via JS.
"""
import time
from pathlib import Path

from SeleniumLibrary import SeleniumLibrary

PAGES = Path(__file__).parents[1] / "dom-edge-cases" / "pages"

sl = SeleniumLibrary()
sl.open_browser(f"file://{PAGES}/shadow.html", "headlesschrome")
driver = sl.driver
print("driver acquired:", type(driver).__name__)

from selenium.webdriver.common.by import By

print("count css:", len(driver.find_elements(By.CSS_SELECTOR, "#status")))
print("count missing:", len(driver.find_elements(By.CSS_SELECTOR, "#nope")))
el = driver.find_elements(By.CSS_SELECTOR, "#status")[0]
print("visible:", el.is_displayed(), "| text:", el.text[:20])
print("readyState:", driver.execute_script("return document.readyState"))
print("innerText via js:", driver.execute_script("return arguments[0].innerText", el)[:20])
print("viewport check:", driver.execute_script(
    "const r=arguments[0].getBoundingClientRect();"
    "return r.bottom>0 && r.top<window.innerHeight", el))
driver.execute_script("arguments[0].scrollIntoView({block:'center'})", el)
print("scrollIntoView: ok")
png = driver.get_screenshot_as_png()
print("screenshot bytes:", len(png), png[:4] == b"\x89PNG")
src = driver.page_source
print("page source:", len(src), "| pierces shadow:", "shadow-submit" in src)
shadow_html = driver.execute_script("""
  function ser(node){
    let html="";
    if(node.nodeType===Node.ELEMENT_NODE){
      html += "<"+node.tagName.toLowerCase()+">";
      if(node.shadowRoot){ html += ser(node.shadowRoot); }
      else { for(const c of node.childNodes) html += ser(c); }
      html += "</"+node.tagName.toLowerCase()+">";
    } else if(node.nodeType===Node.DOCUMENT_FRAGMENT_NODE){
      for(const c of node.childNodes) html += ser(c);
    } else if(node.nodeType===Node.TEXT_NODE){ html += node.textContent; }
    return html;
  }
  return ser(document.documentElement);
""")
print("JS shadow serialization pierces:", "Submit deep" in shadow_html)

# SL keyword locator prefixes
try:
    sl.page_should_contain_element("css:#status")
    print("SL 'css:' prefix: ok")
except Exception as exc:
    print("SL 'css:' prefix FAIL:", str(exc)[:60])
try:
    sl.page_should_contain_element("xpath://p[@id='status']")
    print("SL 'xpath:' prefix: ok")
except Exception as exc:
    print("SL 'xpath:' prefix FAIL:", str(exc)[:60])

# fill via clear+send_keys (input lives inside shadow DOM here, use a plain page)
sl.go_to(f"file://{PAGES}/frame_inner.html")
time.sleep(0.3)
email = driver.find_elements(By.CSS_SELECTOR, "#frame-email")[0]
email.clear(); email.send_keys("probe@example.com")
print("fill via clear+send_keys:", email.get_attribute("value"))

sl.close_all_browsers()
print("DONE")
